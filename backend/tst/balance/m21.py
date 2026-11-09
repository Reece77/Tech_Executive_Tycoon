"""M21's balance runs (docs/formulas.md 38.5): history holds, the edge is expensive, use
decides, yield learns, own fabs pay a chip company, nothing else moves. Printed by
tools/m21_targets.py.

Runs are real games (`tst.balance.game`): a fab ordered through `build_fab`, staffed by a unit
of fab engineers at a set skill, and (where a run measures a running fab) made ready at once
from its order month: construction, EUV tools and the overrun are tested elsewhere.
"""

from __future__ import annotations

import statistics as st
from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path

from tst.balance.game import Game, start_game
from tst.loader import LoadedData, load_all
from tst.sim.actions.facilities import StaffFacility
from tst.sim.calendar import ym_to_turn
from tst.sim.fabs import formulas as fx
from tst.sim.fabs import market as fm
from tst.sim.fabs import nodes as nd
from tst.sim.fabs.actions import BuildFab, quote
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH, PPE
from tst.sim.org.models import OrgUnit
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.research.models import ResearchLead
from tst.sim.rng import RngFactory
from tst.sim.state import (
    with_employment,
    with_fab,
    with_facility,
    with_person,
    with_person_state,
    with_research_lead,
    with_unit,
)

DATA = Path(__file__).resolve().parents[2] / "data"
PLAYER = 1
RICH = 10**15  # cents: cash is never the constraint in these runs
SKILL = 12.0  # the fab engineers' manufacturing skill (38.5 target 4)
SALARY = 9_500_000  # a mid fab engineer's salary, cents a year (roles.yaml)
LEAD = 30.0  # a process lead as if researched: every node's need is met


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


def game_at(seed: int, turn: int, *, lead: float = LEAD) -> Game:
    g = start_game(loaded(), seed, "funded_spinout")
    g.balances[(PLAYER, CASH)] = g.balances.get((PLAYER, CASH), 0) + RICH
    g.state = replace(g.state, turn=turn)
    domain = loaded().balance.refining.domain
    g.state = with_research_lead(g.state, ResearchLead(PLAYER, domain, lead))
    return g


def hire_unit(game: Game, name: str, n: int, skill: float = SKILL, seed: int = 1) -> int:
    """A team of `n` fab engineers at manufacturing skill `skill`; its unit id."""
    state = game.state
    lg = loaded()
    role = lg.game_data.role("fab_engineer")
    uid, ids = state.next_ids.take("unit")
    state = replace(state, next_ids=ids)
    state = with_unit(
        state,
        OrgUnit(
            id=uid,
            company_id=PLAYER,
            kind="team",
            name=name,
            parent_id=None,
            leader_id=None,
            policy=None,
            created_turn=state.turn,
        ),
    )
    rng = RngFactory(seed)
    for i in range(n):
        pid, ids = state.next_ids.take("person")
        eid, ids = ids.take("employment")
        state = replace(state, next_ids=ids)
        person = generate_person(
            rng.stream(0, "misc", 700 + uid * 1000 + i),
            lg.game_data,
            lg.balance,
            state.turn,
            role,
            "mid",
            "north_america",
            person_id=pid,
        )
        person = replace(person, skills=person.skills.updated({"manufacturing": skill}))
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(
                id=eid,
                person_id=pid,
                company_id=PLAYER,
                role="fab_engineer",
                level="mid",
                salary_cents=SALARY,
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
                unit_id=uid,
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=65.0))
    game.state = state
    return uid


def build(
    game: Game,
    node: str,
    region: str,
    capacity: int,
    *,
    ready_now: bool = True,
    skill: float = SKILL,
    duv: bool = False,
) -> int:
    """Order and staff (full coverage) a fab and, by default, finish it now. Its facility id."""
    b = loaded().balance
    kind = b.facility.kinds["fab"]
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))
    fid = game.state.next_ids.facility
    ok = game.act(BuildFab(game.founder_id, node, region, capacity, duv=duv))
    if not ok:
        raise RuntimeError(f"build_fab refused: {dict(game.refused)}")
    need = -(-capacity // int(kind.staff_per))
    uid = hire_unit(game, f"fab {fid}", need, skill, seed=fid)
    game.state = with_person_state(game.state, replace(ps, energy=100))
    game.act(StaffFacility(game.founder_id, fid, uid))
    game.notes[f"staff:{fid}"] = uid
    if ready_now:
        make_ready(game, fid)
    return fid


def make_ready(game: Game, fid: int) -> None:
    """Built and paid for now: capex to PPE, live from this month (tools waived)."""
    f = game.state.facility(fid)
    fab = fm.fab_of(game.state, fid)
    assert f is not None and fab is not None
    turn = game.state.turn
    game.state = with_facility(
        game.state,
        replace(f, ordered_turn=turn - fab.build_months, capex_paid_cents=f.capex_cents),
    )
    game.state = with_fab(game.state, replace(fab, live_turn=turn, tools_turn=None))
    game.balances[(PLAYER, CASH)] = game.balances.get((PLAYER, CASH), 0) - f.capex_cents
    game.balances[(PLAYER, PPE)] = game.balances.get((PLAYER, PPE), 0) + f.capex_cents


def keep_staffed(game: Game, skill: float = SKILL) -> None:
    from tst.sim.facilities import lifecycle

    b = loaded().balance
    for f in list(game.state.facilities):
        uid = game.notes.get(f"staff:{f.id}")
        if uid is None or f.status == "closed":
            continue
        s = lifecycle.staffing(game.state, f, b)
        if s.staff < s.needed:
            _top_up(game, uid, s.needed - s.staff, skill, f.id)


def _top_up(game: Game, uid: int, n: int, skill: float, seed: int) -> None:
    state = game.state
    lg = loaded()
    role = lg.game_data.role("fab_engineer")
    rng = RngFactory(seed)
    for i in range(n):
        pid, ids = state.next_ids.take("person")
        eid, ids = ids.take("employment")
        state = replace(state, next_ids=ids)
        person = generate_person(
            rng.stream(state.turn, "misc", pid, i),
            lg.game_data,
            lg.balance,
            state.turn,
            role,
            "mid",
            "north_america",
            person_id=pid,
        )
        person = replace(person, skills=person.skills.updated({"manufacturing": skill}))
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(
                id=eid,
                person_id=pid,
                company_id=PLAYER,
                role="fab_engineer",
                level="mid",
                salary_cents=SALARY,
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
                unit_id=uid,
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=65.0))
    game.state = state


def play(game: Game, n: int = 1) -> None:
    for _ in range(n):
        keep_staffed(game)
        game.turn()


def seeds(n: int) -> Sequence[int]:
    return range(1, n + 1)


# --- Target 1: history holds -----------------------------------------------------------------


def history_misses(seed: int) -> list[str]:
    """Every (foundry, node) date in nodes.yaml against the seed's timeline."""
    lg = loaded()
    nf = lg.game_data.nodes
    assert nf is not None
    tl = nd.timeline(seed, nf, lg.balance.fab)
    from tst.sim.facilities.config import month_to_turn

    misses = []
    for f in nf.foundries:
        for n in nf.nodes:
            month = f.reaches.get(n.key) or n.first.get(f.key)
            if month is None:
                if tl.reach.get((f.key, n.key), nd.NEVER) <= nd.HISTORY_END:
                    misses.append(f"{f.key} {n.key}: reached but not in history")
                continue
            if tl.reach.get((f.key, n.key)) != month_to_turn(month):
                misses.append(f"{f.key} {n.key}: {tl.reach.get((f.key, n.key))} != {month}")
    return misses


# --- Target 2: the edge is expensive ---------------------------------------------------------


@dataclass(frozen=True)
class Capex:
    node: str
    lo: int  # the quote at no overrun
    hi: int  # at the most overrun


def capex_range(node: str, year: int, starts: int = 50_000) -> Capex:
    lg = loaded()
    game = game_at(1, ym_to_turn(year, 1))
    q = quote(game.state, PLAYER, node, "east_asia", starts, lg.balance, lg.game_data)
    o = lg.balance.fab.overrun
    return Capex(node, round(q.capex_cents * (1 + o.lo)), round(q.capex_cents * (1 + o.hi)))


# --- Target 3: use decides (a project's cash flows from a real fab's months) ----------------


@dataclass(frozen=True)
class FabRun:
    node: str
    start: tuple[int, int]
    use: float
    capex_cents: int
    months: tuple[tuple[int, float, float, float, float, int, int], ...]
    # (turn, yield, available, market cents, cost cents w/o depreciation, revenue cents, fixed)


def fab_run(
    seed: int,
    node: str,
    start: tuple[int, int],
    months: int,
    *,
    starts: int = 50_000,
    region: str = "east_asia",
) -> FabRun:
    """A fab finished at `start` with no chips of its own: every start it runs is a slot."""
    game = game_at(seed, ym_to_turn(*start))
    fid = build(game, node, region, starts)
    f = game.state.facility(fid)
    assert f is not None
    rows = []
    for _ in range(months):
        play(game)
        fab = fm.fab_of(game.state, fid)
        assert fab is not None and fab.month is not None
        m = fab.month
        rows.append(
            (
                m.turn,
                m.yield_,
                m.available,
                m.market_cents,
                float(m.fixed_cents + m.materials_cents + m.power_cents + m.staff_cents),
                m.revenue_cents,
                m.fixed_cents,
            )
        )
    return FabRun(node, start, 0.0, f.capex_cents, tuple(rows))


def project_irr(run: FabRun, use: float, behind: int = 0, build_months: int = 36) -> float | None:
    """Target 3's project IRR: capex spread over construction, then each month's slot revenue
    at `use` of capacity minus its running costs (fixed in full, materials and power by use),
    at a market price `behind` generations older (x (1 - decay)^behind)."""
    b = loaded().balance
    flows = [-run.capex_cents / build_months] * build_months
    decay = (1 - b.fab.price_decay) ** behind
    mature = b.fab.yield_.mature
    for _, y, avail, market, cost, _, fixed in run.months:
        starts = avail * use
        q = min(1.0, y / mature)
        revenue = starts * market * b.fab.slot.discount * decay * q
        run_cost = (cost - fixed) / max(1.0, avail) * starts
        flows.append(revenue - fixed - run_cost)
    return fx.irr(flows)


# --- Target 4: yield learns ------------------------------------------------------------------


def yield_months(
    seed: int, node: str = "n5", start: tuple[int, int] = (2020, 4)
) -> tuple[float, int | None]:
    """A new leading-edge fab live at its node's first volume: (first yield, months to 80%)."""
    game = game_at(seed, ym_to_turn(*start), lead=0.0)
    lg = loaded()
    need = fm.need_level(game.state, node, lg.balance, lg.game_data)
    level = fm.process_level(game.state, PLAYER, lg.balance, lg.game_data)
    domain = lg.balance.refining.domain
    game.state = with_research_lead(
        game.state, ResearchLead(PLAYER, domain, max(0.0, need - level))
    )  # exactly the node's need: no extra lead
    fid = build(game, node, "east_asia", 50_000)
    first, got = None, None
    for m in range(1, 49):
        play(game)
        fab = fm.fab_of(game.state, fid)
        assert fab is not None
        if first is None:
            first = fab.yield_
        if fab.yield_ >= 0.8:  # tunable-exempt: target 4's 80%
            got = m - 1
            break
    assert first is not None
    return first, got


# --- Target 5: own fabs pay a chip company ---------------------------------------------------


@dataclass(frozen=True)
class ChipRun:
    seed: int
    slot_cost: (
        float  # an accelerator's unit cost on its TSMC contract at the node (the same months)
    )
    fab_cost: float  # on the company's own fab
    use: float
    points: float  # quality cap points from the node

    @property
    def cut(self) -> float:
        return 1 - self.fab_cost / self.slot_cost


def chip_run(seed: int, node: str = "n5", start: tuple[int, int] = (2021, 1)) -> ChipRun:
    """A fabless AI-accelerator company (M12b's) on a TSMC wafer contract at `node`, against the
    same company with its own fab at that node sized to its wafers (high use)."""
    from tst.balance import m12b
    from tst.sim.chips import chips
    from tst.sim.fabs import supply as fs

    lg = loaded()
    b, d = lg.balance, lg.game_data
    turn = ym_to_turn(*start)
    game = game_at(seed, turn)
    ref = d.category("chips_ai_accelerator").market("hyperscalers").reference_price_cents
    state, pid = m12b.product(
        game.state, "chips_ai_accelerator", "hyperscalers", ref, "Accelerator", root=True
    )
    state = m12b.hire(state, "hardware_engineer", 10, seed)
    price = chips.index_wafer_cents(state, "ai_accelerator", b, d, "tsmc", node)
    state = m12b.contract(state, pid, "wafer", 9_000, price, turn, 60)
    from tst.sim.state import with_production_contract

    c = next(c for c in state.production_contracts if c.product_id == pid)
    state = with_production_contract(state, replace(c, node=node))
    game.state = state
    product = game.state.product(pid)
    assert product is not None
    fid = build(game, node, "east_asia", 10_000)
    use: list[float] = []
    cost: list[float] = []
    points: list[float] = []
    slots: list[float] = []
    for _ in range(36):
        play(game)
        state = replace(game.state, turn=game.state.turn - 1)  # the month just played
        fab = fm.fab_of(state, fid)
        product = state.product(pid)
        assert fab is not None and fab.month is not None and product is not None
        own = chips.fab_unit_cents(state, product, b, d)
        if own is not None and fab.yield_ >= 0.8:  # past the ramp
            use.append(fab.month.utilization)
            cost.append(own)
            points.append(fm.node_points(state, fs.product_node(state, product, b, d), b, d))
            slots.append(chips.contract_unit_cents(state, product, b, d))
    return ChipRun(
        seed,
        st.mean(slots) if slots else float("nan"),
        st.mean(cost) if cost else float("nan"),
        st.mean(use) if use else 0.0,
        st.mean(points) if points else 0.0,
    )


# --- Target 6: nothing else moves ------------------------------------------------------------


def price_ratio(seed: int, years: Sequence[int] = range(2010, 2026)) -> list[float]:
    """M12b's wafer price through 2025 with the rival foundries' capacity factor, against M12b's
    index price (1.0 means unchanged), January of each year."""
    from tst.sim.chips import chips
    from tst.sim.commodities import costs

    lg = loaded()
    b, d = lg.balance, lg.game_data
    out = []
    game = game_at(seed, 0)
    for y in years:
        state = replace(game.state, turn=ym_to_turn(y, 1))
        with_factor = chips.index_wafer_cents(state, "ai_accelerator", b, d, "tsmc")
        index = costs.cost_index(state, b.chips.good, d, b)
        plain = b.chips.types["ai_accelerator"].wafer_cents * index
        out.append(with_factor / plain)
    return out
