"""A fab's month (docs/formulas.md 38.2).

**Phase 4** (`fab_month`, after the generic facilities): capex is paid in equal parts over
construction (and over a conversion); a fab goes live at the later of construction, its EUV
tools' arrival plus installation, and its node's first volume; a live fab learns yield and
offers `live capacity x staff coverage` starts (`FabMonth.available`).

**Phase 5** (`settle_fabs`, after production): the starts the company's chips used, then
spare starts sold as foundry slots (`slot.take x yield / mature yield x reliability`, all of
them while the foundry market is short) at the node's market price x `slot.discount` to
4420; the month's costs: depreciation (6700) on each part of capex from the month it went
live over the kind's life, and fixed running cost, materials (substrate wafer, gases and
chemicals moving with neon, gallium and germanium) and power at the region's index to 5000.
The lead engineers' pay is in payroll; it is counted in the cost a start for the screen and
the chip's cost per good die.

A fab at 7 nm by DUV runs at fab.duv's yield and cost multipliers.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import format_turn
from tst.sim.commodities import commodity
from tst.sim.data_models import Balance, GameData
from tst.sim.fabs import formulas as fx
from tst.sim.fabs import market as fm
from tst.sim.fabs.draws import YIELD, fab_draws
from tst.sim.fabs.models import CapexPart, Fab, FabMonth
from tst.sim.facilities import formulas as ff
from tst.sim.facilities import lifecycle
from tst.sim.facilities.models import Facility
from tst.sim.group.assets import inbox_company
from tst.sim.ledger import (
    ACCUMULATED_DEPRECIATION,
    CASH,
    COGS,
    DEPRECIATION,
    FOUNDRY_SALES,
    INTERCOMPANY_PURCHASES,
    INTERCOMPANY_SALES,
    PPE,
    LedgerEntry,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import exact
from tst.sim.refining import goods as rg
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_fab, with_facility

MONTHS: Final = 12
PERCENT: Final = 100


def facility_of(state: GameState, fab: Fab) -> Facility:
    f = state.facility(fab.facility_id)
    assert f is not None
    return f


def fab_name(state: GameState, fab: Fab, balance: Balance, data: GameData) -> str:
    return lifecycle.facility_name(facility_of(state, fab), balance, data)


def node_label(data: GameData, node: str) -> str:
    nf = fm.nodes_file(data)
    n = nf.node(node)
    if n is not None:
        return n.label
    fut = nf.future_node(node)
    return fut.label if fut is not None else node


def cost_mult(fab: Fab, balance: Balance) -> float:
    return balance.fab.duv.cost_mult if fab.duv else 1.0


def yield_mult(fab: Fab, balance: Balance) -> float:
    return balance.fab.duv.yield_mult if fab.duv else 1.0


def is_live(fab: Fab, facility: Facility, turn: int) -> bool:
    return facility.status == "live" and not fab.upgrading(turn) and turn >= fab.live_turn


def has_live_fab(state: GameState, company_id: int, balance: Balance) -> bool:
    """A live fab in the company's group (M23a: a sister company's fab supplies it too)."""
    from tst.sim.refining.plants import group_of

    group = group_of(state, company_id)
    return any(
        f.company_id in group and is_live(f, facility_of(state, f), state.turn) for f in state.fabs
    )


def depreciation_total(fab: Fab, turn: int, life: int) -> int:
    """Accumulated straight-line depreciation of each live part, never above its cost."""
    total = 0
    for p in fab.parts:
        months = max(0, turn - p.live_turn + 1)
        total += min(p.cents, p.cents * months // life)
    return total


# --- Phase 4 ---------------------------------------------------------------------------------


def _pay_capex(
    state: GameState, fab: Fab, facility: Facility, balance: Balance, data: GameData
) -> tuple[Facility, Fab, list[LedgerEntry]]:
    turn = state.turn
    entries: list[LedgerEntry] = []
    name = lifecycle.facility_name(facility, balance, data)
    build_end = facility.ordered_turn + fab.build_months
    if facility.status == "building" and turn < build_end:
        pay = ff.capex_payment_cents(
            facility.capex_cents,
            fab.build_months,
            facility.capex_paid_cents,
            turn - facility.ordered_turn,
        )
        if pay:
            entries.append(_capex(turn, facility.company_id, f"Capex: {name}", pay))
            facility = replace(facility, capex_paid_cents=facility.capex_paid_cents + pay)
    if (
        fab.upgrade_started is not None
        and fab.upgrade_ready is not None
        and turn < fab.upgrade_ready
    ):
        months = fab.upgrade_ready - fab.upgrade_started
        pay = ff.capex_payment_cents(
            fab.upgrade_cents, months, fab.upgrade_paid_cents, turn - fab.upgrade_started
        )
        if pay:
            entries.append(_capex(turn, facility.company_id, f"Capex: converting {name}", pay))
            facility = replace(facility, capex_paid_cents=facility.capex_paid_cents + pay)
            fab = replace(fab, upgrade_paid_cents=fab.upgrade_paid_cents + pay)
    return facility, fab, entries


def _capex(turn: int, company: int, memo: str, amount: int) -> LedgerEntry:
    return LedgerEntry.transfer(
        turn=turn, company_id=company, memo=memo, debit=PPE, credit=CASH, amount=amount
    )


def _go_live(
    state: GameState, fab: Fab, facility: Facility, balance: Balance, data: GameData
) -> tuple[Facility, Fab, list[LogItem]]:
    turn = state.turn
    logs: list[LogItem] = []
    name = lifecycle.facility_name(facility, balance, data)
    build_end = facility.ordered_turn + fab.build_months
    if facility.status == "building" and turn >= build_end:
        if turn < fab.live_turn or not fm.in_volume(state, fab.node, balance, data):
            if turn == build_end and fab.tools_turn is not None:
                logs.append(
                    inbox_item(
                        turn,
                        inbox_company(state, facility.company_id),
                        "fab_waiting_tools",
                        link_kind="fab",
                        link_id=facility.id,
                        fab=name,
                        supplier=fm.nodes_file(data).euv.supplier,
                        tools=_month(fab.tools_turn),
                        ready=_month(fab.live_turn),
                    )
                )
            return facility, fab, logs
        facility = replace(facility, status="live", ready_turn=turn, late_turn=turn)
        start = _start_yield(state, fab, balance, data)
        fab = replace(
            fab,
            live_turn=turn,
            yield_=start,
            months_run=0,
            parts=(*fab.parts, CapexPart(facility.capex_paid_cents, turn)),
        )
        logs.append(_live_log(state, facility, fab, name, data, "fab_live"))
    if fab.upgrade_ready is not None and turn >= fab.upgrade_ready and fab.upgrade_node:
        new = fab.upgrade_node
        fab = replace(
            fab,
            node=new,
            upgrade_node=None,
            upgrade_ready=None,
            upgrade_started=None,
            parts=(*fab.parts, CapexPart(fab.upgrade_paid_cents, turn)),
            upgrade_cents=0,
            upgrade_paid_cents=0,
            months_run=0,
        )
        fab = replace(fab, yield_=_start_yield(state, fab, balance, data), live_turn=turn)
        logs.append(_live_log(state, facility, fab, name, data, "fab_upgraded"))
    return facility, fab, logs


def _month(turn: int | None) -> str:
    return format_turn(turn) if turn is not None and turn < fm.NEVER else "not yet known"


def _live_log(
    state: GameState, facility: Facility, fab: Fab, name: str, data: GameData, template: str
) -> LogItem:
    return inbox_item(
        state.turn,
        inbox_company(state, facility.company_id),
        template,
        link_kind="fab",
        link_id=facility.id,
        fab=name,
        node=node_label(data, fab.node),
        yield_pct=f"{fab.yield_:.0%}",
    )


def _start_yield(state: GameState, fab: Fab, balance: Balance, data: GameData) -> float:
    yb = balance.fab.yield_
    age = fm.age_months(state, fab.node, balance, data)
    start = fx.yield_start(age, balance.fab.mature_age_months, yb.start_leading, yb.start_mature)
    return start * yield_mult(fab, balance)


def _learn(
    state: GameState,
    fab: Fab,
    facility: Facility,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> Fab:
    yb = balance.fab.yield_
    staff = lifecycle.staffing(state, facility, balance)
    lead = fm.process_level(state, fab.company_id, balance, data) - fm.need_level(
        state, fab.node, balance, data
    )
    rate = fx.learn_rate(yb.learn, staff.mean_skill, yb.skill_ref, lead, yb.lead_bonus, yb.lead_cap)
    rate *= staff.coverage
    mature = yb.mature * yield_mult(fab, balance)
    value = fx.next_yield(fab.yield_, mature, rate)
    noise = float(fab_draws(rng, state.turn, YIELD, facility.id).normal(0.0, yb.noise_sd))
    value = min(yb.bounds.hi, max(yb.bounds.lo, value * (1 + noise)))
    return replace(fab, yield_=value, months_run=fab.months_run + 1)


def fab_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Phase 4: every fab's capex, completion, conversion and yield; its starts on offer."""
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for fab in state.fabs:
        facility = facility_of(state, fab)
        if facility.status == "closed":
            continue
        facility, fab, more = _pay_capex(state, fab, facility, balance, data)
        entries += more
        facility, fab, notes = _go_live(state, fab, facility, balance, data)
        logs += notes
        month = FabMonth(turn=state.turn)
        state = with_facility(state, facility)
        if is_live(fab, facility, state.turn):
            if fab.months_run > 0 or fab.live_turn < state.turn:
                fab = _learn(state, fab, facility, rng, balance, data)
            staff = lifecycle.staffing(state, facility, balance)
            month = replace(
                month,
                available=facility.capacity * staff.coverage,
                yield_=fab.yield_,
                reliability=staff.reliability,
            )
        state = with_fab(state, replace(fab, month=month))
    return state, entries, logs


# --- Phase 5 ---------------------------------------------------------------------------------


def materials_cents(
    state: GameState, fab: Fab, balance: Balance, data: GameData, *, public: bool = False
) -> float:
    """A start's substrate wafer and gases and chemicals (38.2). `public`: at the node's
    planning wafer price (a quote, M23a), not an unarrived node's seeded one."""
    mb = balance.fab.materials
    substrate = rg.price_cents(state, mb.substrate_good, balance, data)
    mix = sum(w * commodity.index_now(state, g, data) for g, w in mb.mix.items())
    if public:
        wafer = fm.planning_economics(state, fab.node, balance, data)[1]
    else:
        wafer = fm.timeline(state, balance, data).wafer_cents[fab.node]
    chemicals = mb.chemicals_share * wafer * mix
    return (substrate + chemicals) * cost_mult(fab, balance)


def _power_cents(
    state: GameState, fab: Fab, facility: Facility, balance: Balance, data: GameData
) -> float:
    from tst.sim.commodities import power

    tl = fm.timeline(state, balance, data)
    pm = balance.fab.power_mwh
    mwh = fx.power_mwh(pm.base, pm.per_generation, tl.generation(fab.node))
    return mwh * balance.refining.power_cents_per_mwh * power.index(state, facility.region, data)


def _customers(data: GameData, starts: float) -> tuple[tuple[str, float], ...]:
    """The rival fabless designers buying the slots (38.2), in incumbents.yaml order: the chip
    incumbents, equally (the screen's list; their own costs are abstract)."""
    names = [
        c.name
        for c in data.incumbents
        if any(data.category(p.category).chip_type is not None for p in c.products)
    ]
    if not names or starts <= 0:
        return ()
    return tuple((n, starts / len(names)) for n in names)


def settle_fabs(
    state: GameState,
    own_starts: dict[int, float],
    balance: Balance,
    data: GameData,
    buyers: dict[tuple[int, int], float] | None = None,
) -> tuple[GameState, list[LedgerEntry]]:
    """Phase 5: each fab's own use, foundry slots and costs (module docstring). `buyers`:
    (fab, company) -> the starts the group's chip products of that company used (M23a); a
    sister company pays the fab's owner for them at the transfer price (4300 / 5900)."""
    entries: list[LedgerEntry] = []
    life = balance.facility.kinds[fab_kind(balance)].life_months
    fb = balance.fab
    short = fm.allocation_factor(state, balance, data) < 1 or _chips_short(state, data, balance)
    for fab in state.fabs:
        facility = facility_of(state, fab)
        month = fab.month if fab.month is not None and fab.month.turn == state.turn else None
        if facility.status == "closed" or month is None:
            continue
        name = lifecycle.facility_name(facility, balance, data)
        company = facility.company_id
        turn = state.turn
        dep_total = depreciation_total(fab, turn, life)
        dep = dep_total - facility.depreciated_cents
        if dep > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=company,
                    memo=f"Depreciation: {name}",
                    debit=DEPRECIATION,
                    credit=ACCUMULATED_DEPRECIATION,
                    amount=dep,
                )
            )
            facility = replace(facility, depreciated_cents=dep_total)
        live = month.available > 0
        own = min(month.available, own_starts.get(fab.facility_id, 0.0)) if live else 0.0
        spare = max(0.0, month.available - own)
        quality = min(1.0, fab.yield_ / (fb.yield_.mature * yield_mult(fab, balance)))
        take = 1.0 if short else fb.slot.take * quality * month.reliability / PERCENT
        sold = spare * take if live else 0.0
        market = fm.node_price_cents(state, fab.node, balance, data)
        slot = market * fb.slot.discount
        revenue = round(sold * slot)
        run = own + sold
        fixed = fixed_cents(fab, facility, balance)
        materials = round(run * materials_cents(state, fab, balance, data))
        power_ = round(run * _power_cents(state, fab, facility, balance, data))
        staff = sum(e.salary_cents for e in lifecycle.staff_of(state, facility, balance)) // MONTHS
        cash = fixed + materials + power_
        if cash:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=company,
                    memo=f"Fab operations: {name}",
                    debit=COGS,
                    credit=CASH,
                    amount=cash,
                )
            )
        if revenue:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=company,
                    memo=f"Foundry slots: {name}",
                    debit=CASH,
                    credit=FOUNDRY_SALES,
                    amount=revenue,
                )
            )
        total = max(0, dep) + cash + staff
        per_start = total / run if run > 0 else 0.0
        group, more = _group_supply(state, fab, own, per_start, market, buyers or {}, name, balance)
        entries += more
        month = replace(
            month,
            own=own,
            sold=sold,
            depreciation_cents=max(0, dep),
            fixed_cents=fixed,
            materials_cents=materials,
            power_cents=power_,
            staff_cents=staff,
            revenue_cents=revenue,
            slot_price_cents=slot,
            market_cents=market,
            cost_per_start_cents=per_start,
            customers=_customers(data, sold),
            group=group,
        )
        history = fab.history
        if live:
            keep = fb.history_months
            row = (turn, fab.yield_, month.utilization, per_start, market)
            history = (*history, row)[-keep:]
        state = with_facility(state, facility)
        state = with_fab(state, replace(fab, month=month, history=history))
    return state, entries


def fixed_cents(fab: Fab, facility: Facility, balance: Balance) -> int:
    """The month's fixed running cost (38.6): fab.fixed_share of the capex that has gone live,
    a year, for as long as the facility is live, staffed or not (M23a, Codex review 5 finding
    6). A conversion's capex joins it when the conversion goes live; offline while converting,
    the fab keeps paying it on the capex already live (M23a decision)."""
    if facility.status != "live":
        return 0
    live = sum(p.cents for p in fab.parts)
    return round(exact(live) * exact(balance.fab.fixed_share) / MONTHS)


def _group_supply(
    state: GameState,
    fab: Fab,
    own: float,
    per_start: float,
    market: float,
    buyers: dict[tuple[int, int], float],
    name: str,
    balance: Balance,
) -> tuple[tuple[tuple[int, float, float, float], ...], list[LedgerEntry]]:
    """The month's starts by group company (M23a): a sister company pays the fab's owner the
    transfer price (31.6: the `chips` flow's, cost by default: this month's cost a start) for
    the starts its chips used; consolidation removes both sides."""
    from tst.sim.fabs.supply import FLOW_GOOD
    from tst.sim.group import formulas as gf
    from tst.sim.group.transfer import flow_of

    used = {cid: n for (fid, cid), n in sorted(buyers.items()) if fid == fab.facility_id}
    total = sum(used.values())
    if total <= 0 or own <= 0:
        return (), []
    scale = min(1.0, own / total)  # the starts the fab actually ran for the group
    rows: list[tuple[int, float, float, float]] = []
    entries: list[LedgerEntry] = []
    seller = fab.company_id
    for cid, n in used.items():
        starts = n * scale
        cost = round(starts * per_start)
        value = round(starts * market)
        price = cost
        flow = flow_of(state, seller, cid, FLOW_GOOD) if cid != seller else None
        if flow is not None:
            price = gf.transfer_price_cents(flow.kind, cost, value, balance, flow.margin)
        if cid != seller and price > 0:
            buyer = state.company(cid).name
            entries += [
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=cid,
                    memo=f"Fab starts from {state.company(seller).name}: {name}",
                    debit=INTERCOMPANY_PURCHASES,
                    credit=CASH,
                    amount=price,
                ),
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=seller,
                    memo=f"Fab starts for {buyer}: {name}",
                    debit=CASH,
                    credit=INTERCOMPANY_SALES,
                    amount=price,
                ),
            ]
        rows.append((cid, starts, float(price), float(value)))
    return tuple(rows), entries


def _chips_short(state: GameState, data: GameData, balance: Balance) -> bool:
    from tst.sim.facilities import goods

    return goods.allocation_now(state, balance.chips.good, data) < 1


def fab_kind(balance: Balance) -> str:
    return FAB_KIND


FAB_KIND: Final = "fab"  # facility.kinds key (38.2)
