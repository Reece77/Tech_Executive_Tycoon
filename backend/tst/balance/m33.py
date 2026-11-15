"""M33's balance targets (docs/formulas.md 47.5), printed by tools/m33_targets.py.

1. History holds: tests (tests/unit/test_m33_equipment.py: every year 2010-2025 delivers
   equipment.yaml's shipments; prices, generations and dated controls follow it) and every
   earlier guard re-run.
2. The queue is real (an equipment-only run: rivals' orders as the game makes them, ASML's
   December rule from 2026): a player order of a 25,000-start fab's tools (13 low-NA tools)
   placed in January, April, July, October or December of 2027-2032. A tool's wait is the months
   from the order to its delivery; a buyer's median wait is the median over its tools. A new
   buyer has no deliveries; a long-standing one had 20 in the last 5 years. At least 18 months
   for the new buyer and at most 12 for the long-standing one; and a buyer under a tool ban
   (SMIC, the player in China) gets none.
3. The long bet rarely pays early (an equipment-only run with a real lab: 160 senior hardware
   engineers on a lithography project, the level requirements met as if researched): the
   programme starts in January 2028 at the 60th percentile of funding
   (`funding.lo + 0.6 x (hi - lo)`), each stage starting the month the previous one works and
   a failed stage started again at once; it reaches `litho_2` by December 2039 on 2-5 of 10
   seeds. When it does, the cost per good die on its own tools 5 years later (a 25,000-start
   fab's own tools installed from the start: the learning curve) is within 15% of ASML-equipped.
4. China under controls: a Chinese foundry reaches a node that needs EUV only with EUV-class
   tools (tst.sim.equipment.china); while the bans hold, ASML's never reach it, so its EUV-class
   capability is its own tools' month. Measured against the leaders' first EUV-only node (TSMC's
   5 nm, April 2020): median at least 8 years (seeds 1-10).
5. Turn time: `make check-timing` (tests/timing).
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from typing import Final

from tst.balance.m28 import SEEDS, loaded
from tst.balance.report import Row, table
from tst.sim.calendar import ym_to_turn
from tst.sim.equipment import china as echina
from tst.sim.equipment import data as ed
from tst.sim.equipment import programme as ep
from tst.sim.equipment import queue as eq
from tst.sim.equipment.models import Delivery, OwnTools, ToolOrder
from tst.sim.equipment.phase import equipment_month
from tst.sim.research.models import ResearchLead, ResearchProject
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import GameState, with_research_lead, with_research_project

PLAYER: Final = 1
FAB_TOOLS: Final = 13  # a 25,000-start fab: ceil(25,000 / fab.euv.wafers_per_tool)
ORDER_MONTHS: Final = (0, 3, 6, 9, 11)  # January, April, July, October, December
QUEUE_YEARS: Final = range(2027, 2033)
QUEUE_SEEDS: Final = (1, 2, 3)
HISTORY: Final = 20  # a long-standing buyer's tools over the last 5 years
NEW_WAIT, OLD_WAIT = 18, 12  # months (47.5 target 2)
PROGRAMME_START: Final = ym_to_turn(2028, 1)
PROGRAMME_END: Final = ym_to_turn(2039, 12)
PERCENTILE: Final = 0.6
LAB: Final = 160  # researchers (litho_2 needs 120, litho_3 160)
LEAD: Final = 45.0  # the lithography lead, as if researched (every stage's level met)
DIE_YEARS: Final = 5
DIE_BAND: Final = 0.15
# A tool's share of a fab's cost a start (A, for this measure only: capex is about 60% of a
# leading-edge start's cost and the scanners about a quarter of the capex, 38.2's numbers)
TOOL_COST_SHARE: Final = 0.15
REACH_LOW, REACH_HIGH = 2, 5  # seeds of 10 (47.5 target 3)
CHINA_YEARS: Final = 8.0
LEADER_EUV: Final = ym_to_turn(2020, 4)  # TSMC's 5 nm (nodes.yaml)
MONTHS: Final = 12


def fresh(seed: int, turn: int) -> GameState:
    lg = loaded()
    found = lg.game_data.scenario("ex_big_tech_founders")
    assert found is not None
    state, _ = new_game(
        save_name="m33", master_seed=seed, scenario=found, difficulty="standard",
        company_name="Lithos", founder=DEFAULT_FOUNDER, balance=lg.balance, data=lg.game_data,
    )  # fmt: skip
    return replace(state, turn=turn)


def run(state: GameState, to_turn: int, rng: RngFactory) -> GameState:
    lg = loaded()
    t = state.turn
    while t <= to_turn:
        state = replace(state, turn=t)
        state, _, _ = equipment_month(state, rng, lg.balance, lg.game_data)
        t += 1
    return state


# --- target 2: the queue ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class QueueRun:
    new: tuple[int, ...]  # every tool's wait, new buyer
    old: tuple[int, ...]  # long-standing buyer
    smic: int  # SMIC's deliveries 2026-2032
    china_lost: bool  # a player order to China was lost


def _waits(base: GameState, turn: int, history: bool, rng: RngFactory) -> list[int]:
    st = base
    if history:
        st = replace(st, tool_deliveries=(
            *st.tool_deliveries, Delivery(turn - 2 * MONTHS, eq.PLAYER, "euv_low", HISTORY, PLAYER)
        ))  # fmt: skip
    order = ToolOrder(
        eq.next_order_id(st), eq.PLAYER, "euv_low", FAB_TOOLS, turn, company_id=PLAYER,
        country="us", price_cents=1,
    )  # fmt: skip
    st = run(replace(st, tool_orders=(*st.tool_orders, order), turn=turn + 1), turn + 48, rng)
    out: list[int] = []
    for d in st.tool_deliveries:
        if d.buyer == eq.PLAYER and d.turn > turn and d.source == "asml" and d.company_id == PLAYER:
            out += [d.turn - turn] * d.tools
    return out


def queue_run(seed: int) -> QueueRun:
    rng = RngFactory(seed)
    state = run(fresh(seed, ym_to_turn(2025, 12)), ym_to_turn(2026, 11), rng)
    new: list[int] = []
    old: list[int] = []
    smic = 0
    for year in QUEUE_YEARS:
        for month in ORDER_MONTHS:
            turn = ym_to_turn(year, month + 1)
            state = run(state, turn - 1, rng)
            base = replace(state, turn=turn)
            new += _waits(base, turn, False, rng)
            old += _waits(base, turn, True, rng)
    smic = sum(d.tools for d in state.tool_deliveries if d.buyer == "smic")
    china = ToolOrder(
        eq.next_order_id(state), eq.PLAYER, "euv_low", 5, state.turn, company_id=PLAYER,
        country="china", price_cents=1,
    )  # fmt: skip
    after = run(replace(state, tool_orders=(*state.tool_orders, china), turn=state.turn + 1),
                state.turn + 6, rng)  # fmt: skip
    lost = next(o for o in after.tool_orders if o.id == china.id).status == "lost"
    return QueueRun(tuple(new), tuple(old), smic, lost)


# --- target 3: the long bet ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BetRun:
    seed: int
    litho1: int | None  # the month each stage worked
    litho2: int | None
    attempts: int
    die_ratio: float | None  # own-tool die cost / ASML's, 5 years after litho_2


def _lab(state: GameState) -> GameState:
    from tst.balance import fixtures

    lg = loaded()
    domain = lg.balance.equipment.programme.domain
    state = with_research_lead(state, ResearchLead(PLAYER, domain, LEAD))
    state, _ = fixtures.hire(
        state, lg, "hardware_engineer", "senior", LAB, "Lithography lab", 18_000_000, 33
    )
    uid = next(u.id for u in state.units if u.name == "Lithography lab")
    pid, ids = state.next_ids.take("research_project")
    return with_research_project(
        replace(state, next_ids=ids), ResearchProject(pid, PLAYER, domain, uid, state.turn)
    )


def funding() -> float:
    f = loaded().balance.equipment.programme.funding
    return f.lo + PERCENTILE * (f.hi - f.lo)


def die_ratio(state: GameState, stage: str) -> float:
    """Own tools' cost per good die / ASML-equipped, `DIE_YEARS` after the stage worked."""
    lg = loaded()
    b, d = lg.balance, lg.game_data
    p = d.equipment.stage(stage) if d.equipment else None
    assert p is not None
    g = d.equipment.generation(p.generation) if d.equipment else None
    assert g is not None
    prog = ep.latest(state, PLAYER, stage)
    assert prog is not None
    line = OwnTools(PLAYER, stage, p.generation)
    t0 = ep.own_throughput(state, line, b)
    own = math.ceil(FAB_TOOLS / t0)
    line = replace(line, tool_months=own * DIE_YEARS * MONTHS)
    t = ep.own_throughput(state, line, b)
    asml_up = ed.uptime(g, state.turn)
    up = ep.own_uptime(state, line, asml_up, b) / asml_up
    cut = ep.own_yield_cut(state, line, b) / 100
    factor = up * max(0.0, 1 - cut / b.fab.yield_.mature)
    tools = math.ceil(FAB_TOOLS / t)
    asml_price = ed.base_price_cents(g, state.turn, b.equipment.price.growth)
    tool_cost = tools * p.tool_cents / (FAB_TOOLS * asml_price)
    return (1 - TOOL_COST_SHARE + TOOL_COST_SHARE * tool_cost) / factor


def bet_run(seed: int) -> BetRun:
    lg = loaded()
    b, d = lg.balance, lg.game_data
    rng = RngFactory(seed)
    state = _lab(fresh(seed, PROGRAMME_START))
    f = funding()
    state = replace(state, programmes=(ep.start(state, PLAYER, "litho_1", f, rng, b, d),))
    worked: dict[str, int] = {}
    attempts = 1
    t = state.turn
    while t <= PROGRAMME_END and "litho_2" not in worked:
        state = replace(state, turn=t)
        state, _, ended = ep.month(state, rng, b, d)
        for prog, outcome in ended:
            if outcome == "succeeded":
                worked[prog.stage] = t
                if prog.stage == "litho_1":
                    nxt = ep.start(replace(state, turn=t + 1), PLAYER, "litho_2", f, rng, b, d)
                    state = replace(state, programmes=(*state.programmes, nxt))
                    attempts += 1
            else:
                again = ep.start(replace(state, turn=t + 1), PLAYER, prog.stage, f, rng, b, d)
                state = replace(state, programmes=(*state.programmes, again))
                attempts += 1
        t += 1
    ratio = die_ratio(state, "litho_2") if "litho_2" in worked else None
    return BetRun(seed, worked.get("litho_1"), worked.get("litho_2"), attempts, ratio)


# --- target 4: China -------------------------------------------------------------------------


def china_years(seed: int) -> float:
    d = loaded().game_data
    return (echina.own_tools_turn(seed, d, "smic") - LEADER_EUV) / MONTHS


# --- the report ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Results:
    queue: tuple[QueueRun, ...]
    bets: tuple[BetRun, ...]
    china: tuple[float, ...]


def run_all(seeds: Sequence[int] = SEEDS, workers: int = 1) -> Results:
    qs = [s for s in QUEUE_SEEDS if s in seeds] or list(seeds)[:1]
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        queue = tuple(pool.map(queue_run, qs))
        bets = tuple(pool.map(bet_run, seeds))
    return Results(queue, bets, tuple(china_years(s) for s in seeds))


def report(r: Results) -> str:
    med = statistics.median
    new = med([w for q in r.queue for w in q.new])
    old = med([w for q in r.queue for w in q.old])
    smic = sum(q.smic for q in r.queue)
    lost = all(q.china_lost for q in r.queue)
    reached = [x for x in r.bets if x.litho2 is not None]
    ratios = [x.die_ratio for x in reached if x.die_ratio is not None]
    china = med(r.china)
    banned = f"SMIC {smic}; China order lost {lost}"
    reach = f"{REACH_LOW}-{REACH_HIGH}"
    dies = ", ".join(f"{x:.2f}" for x in ratios) or "none reached"
    die_ok = all(x <= 1 + DIE_BAND for x in ratios) if ratios else None
    bets = f"{len(reached)}/{len(r.bets)} seeds"
    rows = [
        Row("1", "history holds", "tests: shipments by year", "test_m33_equipment", True),
        Row("2", "new buyer's median wait", f"{new:.0f} months", f">= {NEW_WAIT}", new >= NEW_WAIT),
        Row("2", "long-standing buyer's", f"{old:.0f} months", f"<= {OLD_WAIT}", old <= OLD_WAIT),
        Row("2", "banned buyers' deliveries", banned, "none", smic == 0 and lost),
        Row("3", "litho_2 by 2039", bets, reach, REACH_LOW <= len(reached) <= REACH_HIGH),
        Row("3", "die cost vs ASML after 5y", dies, f"within {DIE_BAND:.0%}", die_ok),
        Row("4", "China's EUV-class lag", f"{china:.1f} years", f">= {CHINA_YEARS:g}",
            china >= CHINA_YEARS),
        Row("5", "turn time", "make check-timing", "the guards", None),
    ]  # fmt: skip
    detail = "\n".join(
        f"  seed {x.seed}: litho_1 {_m(x.litho1)}, litho_2 {_m(x.litho2)}, attempts {x.attempts}"
        for x in r.bets
    )
    return table(rows) + "\n" + detail


def _m(turn: int | None) -> str:
    from tst.sim.calendar import format_turn

    return format_turn(turn) if turn is not None else "not by 2039"
