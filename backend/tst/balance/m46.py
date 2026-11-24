"""M46 sub-task 1 (docs/tasks/M46-v6-balance-pass-one.md): deploying listed capital. Printed by
tests/balance/test_m46_balance.py (nightly).

`listed_planner` is steady_regions plus a hiring plan once listed, with work for every hire:
- marketers into a marketing unit for each product whose brand is below PLAN_BRAND, one more a
  month while the unit is full, up to PLAN_MARKETERS (formulas 11.5: they direct a large budget);
- sellers into a sales unit for each live product whose sales capacity bound new customers last
  month (11.3, 11.7), PLAN_SELLER_STEP more while full, up to PLAN_SELLERS;
- builders for each new-category team while its feature score is below PLAN_FEATURE, two more at
  a time up to PLAN_BUILDERS (11.4: a full feature score has no work for another builder).
Every step hires only while cash exceeds PLAN_RESERVE_MONTHS of costs. steady_regions itself
leaves the cash idle (M43 decision 8), and is the comparison.

Target: the planner's 10-year ARR is at least TARGET_LIFT above steady_regions' (median of the
paired ratios, 10 seeds). The numbers here describe the script, not the game.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from statistics import median
from typing import Final

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.report import SCENARIO, _loaded
from tst.balance.strategies import monthly_cost
from tst.balance.strategies_v2 import _unit, staff_unit, steady_regions
from tst.sim.actions import AssignUnit
from tst.sim.finance.fundraising import arr_cents
from tst.sim.mna import valuation
from tst.sim.products import formulas as pf

SEEDS: Final = tuple(range(1, 11))
TURNS: Final = 120
TARGET_LIFT: Final = 0.05

PLAN_RESERVE_MONTHS: Final = 24  # months of costs kept in hand (steady's runway)
PLAN_BRAND: Final = 95.0  # a product's brand below this has work for a marketer
PLAN_MARKETERS: Final = 10  # marketers a product at most (the lift's cap at mu about 1 each)
PLAN_SELLER_STEP: Final = 2
PLAN_SELLERS: Final = 40  # sellers a product's sales unit at most
PLAN_FEATURE: Final = 98.0  # a feature score below this has work for a builder
PLAN_BUILDERS: Final = 25  # builders a new-category team at most
PLAN_BUILDER_STEP: Final = 2


def _surplus(game: Game) -> bool:
    if not valuation.is_listed(game.state, PLAYER, game.loaded.game_data):
        return False
    return game.cash > PLAN_RESERVE_MONTHS * monthly_cost(game)


def _grow_unit(game: Game, product_id: int, name: str, role: str, step: int, cap: int) -> None:
    """A unit `name` assigned to the product, one `step` larger each month it is full."""
    uid = _unit(game, name)
    if uid is None:
        return
    unit = next(u for u in game.state.active_units(PLAYER) if u.id == uid)
    if unit.product_id != product_id:
        game.act(AssignUnit(game.founder_id, product_id, uid))
    members = sum(1 for e in game.state.staff(PLAYER) if e.unit_id == uid)
    key = f"plan:{name}"
    wanted = game.notes.get(key, 0)
    if members >= wanted and wanted < cap:
        wanted = min(cap, wanted + step)
    game.notes[key] = wanted
    staff_unit(game, name, role, wanted)


def _builders(game: Game) -> None:
    state, data = game.state, game.loaded.game_data
    for i in range(game.notes.get("np_count", 0)):
        uid = _unit(game, f"New product {i + 1} team")
        unit = next((u for u in state.active_units(PLAYER) if u.id == uid), None)
        if unit is None or unit.product_id is None:
            continue
        product = state.product(unit.product_id)
        if product is None:
            continue
        category = data.category(product.category)
        score = pf.feature_score(product.feature_points, category, state.turn)
        key = f"np_team:{i}"
        members = sum(1 for e in state.staff(PLAYER) if e.unit_id == uid)
        if score < PLAN_FEATURE and game.notes[key] < PLAN_BUILDERS and members >= game.notes[key]:
            game.notes[key] = min(PLAN_BUILDERS, game.notes[key] + PLAN_BUILDER_STEP)


def _sellers_and_marketers(game: Game) -> None:
    for product in game.state.company_products(PLAYER):
        if product.status == "live" and any(
            s.capacity_limited for s in game.state.segments_of(product.id)
        ):
            name = f"Sales {product.id}"
            _grow_unit(game, product.id, name, "account_executive", PLAN_SELLER_STEP, PLAN_SELLERS)
        if product.status in ("live", "in_development") and product.brand < PLAN_BRAND:
            _grow_unit(game, product.id, f"Marketing {product.id}", "marketer", 1, PLAN_MARKETERS)


def listed_planner(game: Game) -> None:
    """steady_regions, and once listed a hiring plan with work for every hire (module doc)."""
    surplus = _surplus(game)
    if surplus:
        _builders(game)  # before steady_regions staffs the new-product teams
    steady_regions(game)
    if surplus:
        _sellers_and_marketers(game)


@dataclass(frozen=True, slots=True)
class CapitalRun:
    strategy: str
    seed: int
    arr_cents: int
    cash_cents: int
    staff: int
    listed_turn: int | None


STRATEGIES: Final = {"steady_regions": steady_regions, "listed_planner": listed_planner}


def _play(args: tuple[str, int]) -> CapitalRun:
    name, seed = args
    game = start_game(_loaded("data"), seed, SCENARIO)
    strategy = STRATEGIES[name]
    listed: int | None = None
    for _ in range(TURNS):
        if game.state.ended:
            break
        strategy(game)
        game.turn()
        if listed is None and valuation.is_listed(game.state, PLAYER, game.loaded.game_data):
            listed = game.state.turn
    return CapitalRun(
        name,
        seed,
        arr_cents(game.state, PLAYER, game.loaded.balance),
        game.cash,
        len(game.state.staff(PLAYER)),
        listed,
    )


def run(seeds: tuple[int, ...] = SEEDS, jobs: int = 1) -> list[CapitalRun]:
    plan = [(name, seed) for name in STRATEGIES for seed in seeds]
    if jobs <= 1:
        return [_play(p) for p in plan]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(_play, plan))


def paired_lift(runs: list[CapitalRun]) -> float:
    """Median over seeds of planner ARR / steady_regions ARR, minus 1."""
    idle = {r.seed: r.arr_cents for r in runs if r.strategy == "steady_regions"}
    ratios = [
        r.arr_cents / idle[r.seed]
        for r in runs
        if r.strategy == "listed_planner" and idle.get(r.seed)
    ]
    return median(ratios) - 1 if ratios else float("nan")
