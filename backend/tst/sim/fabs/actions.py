"""Fabs' immediate actions (ADR-0014, docs/formulas.md 38.2): order a fab and convert one to
the next node. Staffing and selling use M12a's facility actions (a fab is a facility).

**Building.** A fab at a node the company may build (`market.orderable`, at its process level:
`market.need_level`), in a region, at one of the kind's sizes. Capex = starts x 12 x capital
per wafer-per-year x fab.capex_scale (x fab.duv.cost_mult for 7 nm by DUV); the true capex is the
quote x (1 + a hidden overrun) drawn once on stream `fab` (key (0, facility id)), revealed only
as it is paid. Construction is 3 years for a node under fab.mature_age_months old, 2 for an
older one. An EUV fab needs its tools, which arrive by `market.tools_turn`; it can complete no
earlier than their arrival plus installation, nor before its node's first volume. The first
monthly payment must be in cash.

**Upgrading.** A live fab converts to the next node (if in volume and within the company's
research) at fab.upgrade.capex_share of a new fab's capex there, offline for
fab.upgrade.months (or until its EUV tools are installed, if later).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import FabRuleError, InsufficientCashError
from tst.sim.fabs import formulas as fx
from tst.sim.fabs import market as fm
from tst.sim.fabs.draws import OVERRUN, fab_draws
from tst.sim.fabs.models import Fab
from tst.sim.fabs.plants import FAB_KIND, fab_name, node_label
from tst.sim.facilities import formulas as ff
from tst.sim.facilities import lifecycle
from tst.sim.facilities.lifecycle import BuildQuote
from tst.sim.group.assets import check_country, inbox_company, managed_facility, place
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.log import inbox_item
from tst.sim.money import times
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_fab, with_facility


@dataclass(frozen=True, slots=True)
class BuildFab:
    actor_id: int
    node: str  # nodes.yaml key
    region: str
    capacity: int  # wafer starts a month
    duv: bool = False  # 7 nm by DUV (38.1)
    city: str | None = None
    company_id: int | None = None  # M23a: a group company the founder builds for (default: own)
    country: str | None = None  # M23a: the country it sits in (default: its city's, the region's)
    kind: Literal["build_fab"] = "build_fab"


@dataclass(frozen=True, slots=True)
class UpgradeFab:
    actor_id: int
    facility_id: int
    kind: Literal["upgrade_fab"] = "upgrade_fab"


type FabAction = BuildFab | UpgradeFab

ACTION_TYPES: Final[dict[str, type]] = {"build_fab": BuildFab, "upgrade_fab": UpgradeFab}


@dataclass(frozen=True, slots=True)
class FabQuote:
    """What the Build dialog shows (no hidden overrun, no future node's month)."""

    node: str
    region: str
    capacity: int
    duv: bool
    euv: bool
    capex_cents: int
    monthly_capex_cents: int
    build_months: int
    tools: int
    tools_turn: int | None  # when its EUV tools would arrive
    physical_turn: int  # construction done and tools installed (engine: when it may go live)
    ready_turn: int  # when it could start production (a future node: its window's midpoint)
    staff_needed: int
    need_level: float
    level: float
    allowed: bool
    reason: str | None


def _check_node(data: GameData, node: str, duv: bool) -> None:
    nf = fm.nodes_file(data)
    if node not in nf.node_keys():
        raise FabRuleError(f"unknown node {node!r}")
    n = nf.node(node)
    if duv and (n is None or not n.duv_route):
        raise FabRuleError("only 7 nm has a DUV route")


def quote(
    state: GameState,
    company: int,
    node: str,
    region: str,
    capacity: int,
    balance: Balance,
    data: GameData,
    *,
    duv: bool = False,
) -> FabQuote:
    _check_node(data, node, duv)
    if region not in data.region_keys:
        raise FabRuleError(f"unknown region {region!r}")
    kind = balance.facility.kinds[FAB_KIND]
    if capacity not in (kind.sizes or ()):
        sizes = ", ".join(f"{s:,}" for s in kind.sizes or ())
        raise FabRuleError(f"a fab has {sizes} {kind.unit}")
    fb = balance.fab
    capital, _ = fm.planning_economics(state, node, balance, data)  # M23a: public numbers only
    capex = fx.capex_cents(capacity, capital, fb.capex_scale, fb.duv.cost_mult if duv else 1.0)
    age = fm.age_months(state, node, balance, data)
    months = fx.build_months(
        age, fb.mature_age_months, fb.build_months.leading, fb.build_months.mature
    )
    euv = fm.uses_euv(data, node, duv)
    tools = fx.tools_needed(capacity, fb.euv.wafers_per_tool) if euv else 0
    tools_at = fm.tools_turn(state, company, tools, balance, data) if euv else None
    physical = _physical(state.turn + months, tools_at, fb.euv.install_months)
    ready = max(physical, fm.planning_turn(state, node, balance, data))
    need = fm.need_level(state, node, balance, data)
    level = fm.process_level(state, company, balance, data)
    reason = None
    if not fm.orderable(state, node, balance, data):
        reason = f"{node_label(data, node)} is not close enough to volume to plan a fab"
    elif level < need:
        reason = (
            f"{node_label(data, node)} needs process research level {need:.0f} (yours {level:.0f})"
        )
    return FabQuote(
        node=node,
        region=region,
        capacity=capacity,
        duv=duv,
        euv=euv,
        capex_cents=capex,
        monthly_capex_cents=-(-capex // months),
        build_months=months,
        tools=tools,
        tools_turn=tools_at,
        physical_turn=physical,
        ready_turn=ready,
        staff_needed=ff.staff_needed(capacity, kind.staff_per),
        need_level=need,
        level=level,
        allowed=reason is None,
        reason=reason,
    )


def _company(state: GameState, actor_id: int, company_id: int | None) -> int:
    """The company a fab is built for: the actor's own, or (the founder only) another company
    of the group (M23a, as M20's refineries)."""
    from tst.sim.refining.plants import group_of

    own = acting_company(state, actor_id)
    if company_id is None or company_id == own:
        return own
    founder = state.founder_of(state.player.id)
    if founder is None or founder.id != actor_id or company_id not in group_of(state, own):
        raise FabRuleError("only the founder builds for another company of the group")
    return company_id


def _physical(build_end: int, tools_at: int | None, install: int) -> int:
    """Construction done and EUV tools installed (38.2)."""
    return build_end if tools_at is None else max(build_end, tools_at + install)


def overrun_share(state: GameState, facility_id: int, balance: Balance) -> float:
    """The hidden overrun (engine only): uniform in fab.overrun."""
    o = balance.fab.overrun
    rng = RngFactory(state.save_meta.master_seed)
    u = float(fab_draws(rng, state.turn, OVERRUN, facility_id).random())
    return o.lo + (o.hi - o.lo) * u


def build_fab(
    state: GameState, action: BuildFab, balance: Balance, data: GameData, balances: LedgerBalances
) -> Outcome:
    company = _company(state, action.actor_id, action.company_id)
    q = quote(
        state, company, action.node, action.region, action.capacity, balance, data, duv=action.duv
    )
    if not q.allowed:
        raise FabRuleError(q.reason or "this fab cannot be built")
    if action.city is not None and (
        not data.has_city(action.city) or data.city(action.city).region != action.region
    ):
        raise FabRuleError(f"{action.city!r} is not a city in that region")
    check_country(data, action.region, action.country)
    if account_balance(balances, company, CASH) < q.monthly_capex_cents:
        raise InsufficientCashError(f"the first capex payment needs {q.monthly_capex_cents} cents")
    state = spend_energy(
        state, action.actor_id, "build_fab", balance, cost=balance.fab.build_energy
    )
    facility_id = state.next_ids.facility
    # the engine's capex: the node's real capital (an unarrived node's seeded draw, which the
    # quote's planning estimate never shows), with the hidden overrun
    real = fx.capex_cents(
        action.capacity,
        fm.timeline(state, balance, data).capital_cents[action.node],
        balance.fab.capex_scale,
        balance.fab.duv.cost_mult if action.duv else 1.0,
    )
    true_capex = times(real, 1 + overrun_share(state, facility_id, balance))
    bq = BuildQuote(
        kind=FAB_KIND,
        region=action.region,
        capacity=action.capacity,
        index=1.0,
        capex_cents=true_capex,
        monthly_capex_cents=q.monthly_capex_cents,
        build_months=q.build_months,
        allocation=1.0,
        on_time=action.capacity,
        late=0,
        late_months=0,
        staff_needed=q.staff_needed,
        contract_id=None,
        contracted=0,
    )
    state, facility = lifecycle.order_build(state, company, bq)
    facility = replace(facility, ready_turn=q.ready_turn, late_turn=q.ready_turn, city=action.city)
    state = place(with_facility(state, facility), "facility", facility.id, action.country)
    fab = Fab(
        facility_id=facility.id,
        company_id=company,
        node=action.node,
        estimate_cents=q.capex_cents,
        build_months=q.build_months,
        duv=action.duv,
        tools=q.tools,
        tools_turn=q.tools_turn,
        live_turn=q.physical_turn,
    )
    state = with_fab(state, fab)
    tools = (
        f"its {q.tools} EUV tools arrive by {_when(q.tools_turn)}"
        if q.tools_turn is not None
        else "it needs no EUV tools"
    )
    log = inbox_item(
        state.turn,
        inbox_company(state, company),
        "fab_ordered",
        link_kind="fab",
        link_id=facility.id,
        fab=fab_name(state, fab, balance, data),
        units=f"{q.capacity:,} wafer starts a month",
        node=node_label(data, action.node) + (" (DUV)" if action.duv else ""),
        region=data.region(action.region).label,
        capex_cents=q.capex_cents,
        months=q.build_months,
        tools=tools,
        staff=q.staff_needed,
    )
    return Outcome(state, (), (log,))


def _when(turn: int | None) -> str:
    return format_turn(turn) if turn is not None and turn < fm.NEVER else "not yet known"


@dataclass(frozen=True, slots=True)
class UpgradeQuote:
    facility_id: int
    old: str
    new: str | None
    capex_cents: int
    months: int
    tools: int
    tools_turn: int | None
    allowed: bool
    reason: str | None


def upgrade_quote(
    state: GameState, company: int, facility_id: int, balance: Balance, data: GameData
) -> UpgradeQuote:
    fab = fm.fab_of(state, facility_id)
    facility = state.facility(facility_id)
    if fab is None or facility is None or facility.company_id != company:
        raise FabRuleError("that is not one of your fabs")
    nf = fm.nodes_file(data)
    keys = nf.node_keys()
    i = keys.index(fab.node)
    new = keys[i + 1] if i + 1 < len(keys) else None
    fb = balance.fab
    reason: str | None = None
    capex = months = tools = 0
    tools_at: int | None = None
    if facility.status != "live" or fab.upgrading(state.turn) or state.turn < fab.live_turn:
        reason = "only a fab in production can convert"
    elif new is None:
        reason = "there is no newer node"
    else:
        q = quote(state, company, new, facility.region, facility.capacity, balance, data)
        capex = round(q.capex_cents * fb.upgrade.capex_share)
        tools = max(0, q.tools - fab.tools)
        tools_at = fm.tools_turn(state, company, tools, balance, data) if tools else None
        months = fb.upgrade.months
        if tools_at is not None:
            months = max(months, tools_at + fb.euv.install_months - state.turn)
        if not fm.in_volume(state, new, balance, data):
            reason = f"{node_label(data, new)} is not in volume yet"
        elif q.level < q.need_level:
            reason = (
                f"{node_label(data, new)} needs process research level {q.need_level:.0f}"
                f" (yours {q.level:.0f})"
            )
    return UpgradeQuote(
        facility_id=facility_id,
        old=fab.node,
        new=new,
        capex_cents=capex,
        months=months,
        tools=tools,
        tools_turn=tools_at,
        allowed=reason is None,
        reason=reason,
    )


def upgrade_fab(
    state: GameState,
    action: UpgradeFab,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    # M23r (finding 2): the founder converts any group fab; its owner pays
    own = acting_company(state, action.actor_id)
    company = managed_facility(state, action.actor_id, action.facility_id, own).company_id
    uq = upgrade_quote(state, company, action.facility_id, balance, data)
    if not uq.allowed or uq.new is None:
        raise FabRuleError(uq.reason or "this fab cannot convert")
    first = -(-uq.capex_cents // uq.months)
    if account_balance(balances, company, CASH) < first:
        raise InsufficientCashError(f"the first capex payment needs {first} cents")
    state = spend_energy(
        state, action.actor_id, "upgrade_fab", balance, cost=balance.fab.upgrade.energy
    )
    fab = fm.fab_of(state, action.facility_id)
    assert fab is not None
    true_capex = times(uq.capex_cents, 1 + overrun_share(state, action.facility_id, balance))
    ready = state.turn + uq.months
    fab = replace(
        fab,
        upgrade_node=uq.new,
        upgrade_ready=ready,
        upgrade_started=state.turn,
        upgrade_cents=true_capex,
        upgrade_paid_cents=0,
        tools=fab.tools + uq.tools,
        tools_turn=uq.tools_turn if uq.tools_turn is not None else fab.tools_turn,
    )
    state = with_fab(state, fab)
    log = inbox_item(
        state.turn,
        inbox_company(state, company),
        "fab_upgrade_ordered",
        link_kind="fab",
        link_id=action.facility_id,
        fab=fab_name(state, fab, balance, data),
        old=node_label(data, uq.old),
        new=node_label(data, uq.new),
        capex_cents=uq.capex_cents,
        months=uq.months,
        ready=format_turn(ready),
    )
    return Outcome(state, (), (log,))


def apply_fab(
    state: GameState,
    action: FabAction,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    match action:
        case BuildFab():
            return build_fab(state, action, balance, data, balances)
        case UpgradeFab():
            return upgrade_fab(state, action, balance, data, balances)
