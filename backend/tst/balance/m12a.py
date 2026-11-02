"""docs/formulas.md 22.7 targets 2-6 (M12a), measured on the engine.

1. Without building, nothing moves: the earlier targets' own tests.
2. Ownership needs utilization: a 2,000-CU general data centre built in January 2016 (the
   typical stage-3 year), its cost per used CU against spot at 80% and 40% use.
3. Spare capacity sells: a company with a staffed 2,000-CU general data centre at 50% own
   use sells its spare (marketing $50,000 a month, prices 0.9 x reference) for 24 months.
4. History bites: the 2021 server shortage and 2023 GPU crunch from history; an AI company
   with 600 GPU CU of own capacity built in January 2021 against the same company on spot,
   gross margin in 2023.
5. The future varies: seeds with a supply shock by 2035.
6. Staffing matters: outages a year at coverage 0.5 and at full coverage with skill 14,
   from the formula and from seeded rolls.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path

from tst.balance.game import Game, start_game
from tst.loader import LoadedData, load_all
from tst.sim.actions import CreateUnit, SellCapacity, SetMarketing, SetPrice, apply_action
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities import compute, goods
from tst.sim.facilities import formulas as ff
from tst.sim.facilities.models import Facility
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import COMPUTE, DEPRECIATION, REVENUE_SUBSCRIPTIONS
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    with_employment,
    with_facility,
    with_person,
    with_person_state,
    with_product,
    with_product_segment,
)

SEEDS = tuple(range(1, 11))
DATA = Path(__file__).resolve().parents[2] / "data"
PLAYER = 1
RICH = 10**13
T3_MONTHS = 24
T3_UNITS = 2000
T3_OWN_CUSTOMERS = 250_000.0  # B2B SaaS SMB customers: 1,000 CU of hosting at $4 each
T3_MARKETING = 5_000_000
T3_PRICE = 0.9
T4_CUSTOMERS = 100.0  # AI enterprise customers: 600 CU of GPU compute
T6_SKILL = 14.0
MONTHS_PER_YEAR = 12


@cache
def _loaded() -> LoadedData:
    return load_all(DATA)


# --- helpers ----------------------------------------------------------------------------------


def live_facility(
    state: GameState, loaded: LoadedData, kind: str, units: int, built: int
) -> GameState:
    """A paid-for facility that went live at `built`, priced at that month's index."""
    k = loaded.balance.facility.kinds[kind]
    index = goods.current(replace(state, turn=built), k.input_good, loaded.game_data).index
    capex = ff.capex_cents(units, k.capex_per_unit_cents, index)
    fid, ids = state.next_ids.take("facility")
    facility = Facility(
        id=fid,
        company_id=PLAYER,
        kind=kind,
        region="north_america",
        capacity=units,
        on_time=units,
        ordered_turn=built - k.build_months,
        ready_turn=built,
        late_turn=built,
        capex_cents=capex,
        input_index=index,
        capex_paid_cents=capex,
        depreciated_cents=ff.cumulative_depreciation_cents(
            capex, units, units, built, built, k.life_months, state.turn - 1
        ),
        status="live",
    )
    return with_facility(replace(state, next_ids=ids), facility)


def staff(state: GameState, loaded: LoadedData, people: int, seed: int) -> GameState:
    """A unit of `people` senior DevOps engineers staffing the last facility."""
    rng = RngFactory(seed)
    out = apply_action(
        state, CreateUnit(PLAYER, "team", "Ops"), rng, loaded.balance, loaded.game_data, {}, seq=1
    )
    state = out.new_state
    unit = max(u.id for u in state.units)
    role = loaded.game_data.role("devops_engineer")
    for i in range(people):
        pid, ids = state.next_ids.take("person")
        eid, ids = ids.take("employment")
        state = replace(state, next_ids=ids)
        person = generate_person(
            rng.stream(0, "misc", i),
            loaded.game_data,
            loaded.balance,
            state.turn,
            role,
            "senior",
            "north_america",
            person_id=pid,
        )
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(
                id=eid,
                person_id=pid,
                company_id=PLAYER,
                role="devops_engineer",
                level="senior",
                salary_cents=14_000_000,
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
                unit_id=unit,
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=65.0))
    return with_facility(state, replace(state.facilities[-1], unit_id=unit))


def product(
    state: GameState, category: str, segment: str, price: int, customers: float
) -> tuple[GameState, int]:
    pid, ids = state.next_ids.take("product")
    p = Product(
        id=pid,
        company_id=PLAYER,
        category=category,
        name="Own",
        status="live",
        quality=60.0,
        feature_points=200.0,
        brand=40.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
    )
    state = replace(with_product(state, p), next_ids=ids)
    return with_product_segment(state, ProductSegment(pid, segment, price, customers)), pid


def _game(seed: int, turn: int) -> Game:
    g = start_game(_loaded(), seed, "funded_spinout")
    g.balances[(PLAYER, "1000_cash")] = g.balances.get((PLAYER, "1000_cash"), 0) + RICH
    g.state = replace(g.state, turn=turn)
    return g


# --- target 2 ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CostRatios:
    index: float
    at_80: float
    at_40: float
    at_full: float


def target_2() -> CostRatios:
    loaded = _loaded()
    k = loaded.balance.facility.kinds["data_centre_general"]
    built = ym_to_turn(2016, 1)
    state = live_facility(_game(1, built + 1).state, loaded, "data_centre_general", T3_UNITS, built)
    f = state.facilities[-1]
    month = ff.monthly_depreciation_cents(f.capex_cents, k.life_months) + (
        f.capacity * k.opex_per_unit_cents
    )
    spot = loaded.balance.compute.goods["compute_general"].spot_cents

    def ratio(use: float) -> float:
        cost = ff.cost_per_used_unit_cents(month, f.capacity * use)
        assert cost is not None
        return cost / spot

    return CostRatios(f.input_index, ratio(0.8), ratio(0.4), ratio(1.0))


# --- target 3 ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SpareRun:
    seed: int
    utilization: tuple[float, ...]  # month by month

    @property
    def reached(self) -> bool:
        return max(self.utilization) >= 0.85


def target_3_run(seed: int) -> SpareRun:
    loaded = _loaded()
    g = _game(seed, ym_to_turn(2016, 1))
    state = live_facility(g.state, loaded, "data_centre_general", T3_UNITS, g.state.turn)
    state = staff(state, loaded, T3_UNITS // 200, seed)
    state, own = product(state, "b2b_saas", "smb", 5000, T3_OWN_CUSTOMERS)
    g.state = state
    g.act(SellCapacity(g.founder_id))
    cloud = compute.capacity_product(g.state, PLAYER, loaded.game_data)
    assert cloud is not None
    g.act(SetMarketing(g.founder_id, cloud.id, T3_MARKETING))
    for m in loaded.game_data.category(cloud.category).markets:
        g.act(
            SetPrice(g.founder_id, cloud.id, m.segment, round(m.reference_price_cents * T3_PRICE))
        )
    facility = g.state.facilities[-1].id
    out = []
    for _ in range(T3_MONTHS):
        seg = g.state.product_segment(own, "smb")
        assert seg is not None
        g.state = with_product_segment(g.state, replace(seg, customers=T3_OWN_CUSTOMERS))
        g.turn()
        alloc = compute.allocate(g.state, PLAYER, loaded.balance, loaded.game_data)
        out.append(alloc.used(facility) / T3_UNITS)
    return SpareRun(seed, tuple(out))


# --- target 4 ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HistoryBites:
    server_shortage: float
    gpu_crunch: float
    margin_own: float
    margin_spot: float
    spot_cents_2023: float
    own_cents_2023: float

    @property
    def margin_gap(self) -> float:
        return self.margin_own - self.margin_spot


def _ai_margin_2023(own: bool) -> tuple[float, float]:
    """(gross margin over 2023, compute cost per CU in December 2023)."""
    loaded = _loaded()
    start = ym_to_turn(2023, 1)
    g = _game(1, start)
    state, pid = product(g.state, "ai_models", "enterprise", 2_500_000, T4_CUSTOMERS)
    market = loaded.game_data.category("ai_models").market("enterprise")
    units = round(T4_CUSTOMERS * market.hosting_cents / 100_000)
    if own:
        state = live_facility(state, loaded, "data_centre_gpu", units, ym_to_turn(2021, 1))
        state = staff(state, loaded, -(-units // 200), 1)
    g.state = state
    accounts = (REVENUE_SUBSCRIPTIONS, COMPUTE, DEPRECIATION)
    before = {acc: g.balances.get((PLAYER, acc), 0) for acc in accounts}
    for _ in range(MONTHS_PER_YEAR):
        seg = g.state.product_segment(pid, "enterprise")
        assert seg is not None
        g.state = with_product_segment(g.state, replace(seg, customers=T4_CUSTOMERS))
        g.turn()
    moved = {acc: g.balances.get((PLAYER, acc), 0) - before[acc] for acc in accounts}
    revenue = -moved[REVENUE_SUBSCRIPTIONS]
    cost = moved[COMPUTE] + moved[DEPRECIATION]
    return (revenue - cost) / revenue, cost / MONTHS_PER_YEAR / units


def target_4() -> HistoryBites:
    loaded = _loaded()
    components = loaded.game_data.components
    assert components is not None
    server, gpu = components.good("server"), components.good("gpu")
    own, own_cost = _ai_margin_2023(True)
    spot, spot_cost = _ai_margin_2023(False)
    return HistoryBites(
        server_shortage=server.index_at(ym_to_turn(2022, 4)) / server.index_at(ym_to_turn(2021, 4))
        - 1,
        gpu_crunch=gpu.index_at(ym_to_turn(2024, 6)) / gpu.index_at(ym_to_turn(2023, 1)) - 1,
        margin_own=own,
        margin_spot=spot,
        spot_cents_2023=spot_cost,
        own_cents_2023=own_cost,
    )


# --- target 5 ---------------------------------------------------------------------------------


def target_5_run(seed: int) -> bool:
    """A supply shock in any good between January 2026 and December 2035."""
    loaded = _loaded()
    components = loaded.game_data.components
    assert components is not None
    state = replace(start_game(loaded, seed, "funded_spinout").state, turn=components.last_turn + 1)
    rng = RngFactory(seed)
    while state.turn <= ym_to_turn(2035, 12):
        state = goods.supply_phase(state, rng, loaded.balance, loaded.game_data)
        if any(g.shock_turn is not None for g in state.supply):
            return True
        state = replace(state, turn=state.turn + 1)
    return False


# --- target 6 ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Outages:
    half_formula: float  # a year
    full_formula: float
    half_rolled: float
    full_rolled: float


def target_6(years: int = 200) -> Outages:
    loaded = _loaded()
    fb = loaded.balance.facility
    base = fb.outage.base

    def per_year(cover: float) -> float:
        rel = ff.reliability(cover, T6_SKILL, fb.reliability_floor, fb.reliability_skill)
        return 12 * ff.outage_chance(rel, base)

    def rolled(cover: float) -> float:
        rel = ff.reliability(cover, T6_SKILL, fb.reliability_floor, fb.reliability_skill)
        chance = ff.outage_chance(rel, base)
        rng = RngFactory(7)
        hits = sum(float(rng.stream(t, "misc", 27).random()) < chance for t in range(12 * years))
        return hits / years

    return Outages(per_year(0.5), per_year(1.0), rolled(0.5), rolled(1.0))


# --- running and reporting ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Results:
    t2: CostRatios
    t3: tuple[SpareRun, ...]
    t4: HistoryBites
    t5: tuple[bool, ...]
    t6: Outages


def run(seeds: Sequence[int] = SEEDS, jobs: int = os.cpu_count() or 1) -> Results:
    with ProcessPoolExecutor(max(1, jobs)) as pool:
        t3 = tuple(pool.map(target_3_run, seeds))
        t5 = tuple(pool.map(target_5_run, seeds))
    return Results(target_2(), t3, target_4(), t5, target_6())


def report(r: Results) -> str:
    t3 = sum(x.reached for x in r.t3)
    rows = [
        f"T2 built Jan 2016 (server index {r.t2.index:.2f}): cost / spot per used CU at 80% "
        f"{r.t2.at_80:.2f} (<= 0.70), at 40% {r.t2.at_40:.2f} (>= 1.20), full {r.t2.at_full:.2f}",
        f"T3 2,000 CU at 50% own use reaches 85% within 24 months: {t3}/{len(r.t3)} seeds "
        "(>= 6/10);"
        f" best by seed {[round(max(x.utilization), 2) for x in r.t3]}",
        f"T4 server shortage {r.t4.server_shortage:+.0%} (20%-40%), GPU crunch "
        f"{r.t4.gpu_crunch:+.0%} (40%-80%)",
        f"T4 AI gross margin 2023: own GPU {r.t4.margin_own:.1%}, spot {r.t4.margin_spot:.1%}, "
        f"gap {100 * r.t4.margin_gap:+.1f} points (>= +15); compute per CU own "
        f"${r.t4.own_cents_2023 / 100:,.0f}, spot ${r.t4.spot_cents_2023 / 100:,.0f}",
        f"T5 seeds with a supply shock by 2035: {sum(r.t5)}/{len(r.t5)} (>= 70%)",
        f"T6 outages a year: coverage 0.5 {r.t6.half_formula:.2f} (rolled {r.t6.half_rolled:.2f};"
        f" >= 1), full at skill 14 {r.t6.full_formula:.2f} (rolled {r.t6.full_rolled:.2f}; <= 0.2)",
    ]
    return "\n".join(rows)
