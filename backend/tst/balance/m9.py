"""docs/formulas.md 19.8 targets 2, 3 and 5 (M9), printed by tools/m9_targets.py and checked
nightly (tests/balance/test_m9_balance.py). Target 4 is a seeded unit test
(tests/unit/test_geo.py) and target 1 is the v1 and M8 runs on the same code.

- Target 2 (expansion lifts the ceiling): blitzscale that launches its live products in
  Europe once its Series A closes and in East Asia at stage 3, with a small office in each
  region for local presence, against the standard blitzscale; median turn-120 ARR.
- Target 3 (cheap talent has a cost): 30 software engineers at their city's market rate in
  a 50-seat office in Bangalore against the same team in San Francisco, monthly cost; and the
  cross-region factor of a product built by both.
- Target 5 (rivals spread): do-nothing runs to turn 120; every region has a live rival
  product in every category.

People added by these scripts are generated on stream `misc` (tests and tools only).
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from statistics import median
from typing import Final

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.m8 import ArmResult, ratio
from tst.balance.report import SCENARIO, _loaded
from tst.balance.strategies import blitzscale, closed_series, do_nothing
from tst.sim.actions import AssignUnit, CreateProduct, CreateUnit
from tst.sim.actions.geo import LaunchInRegion, LeaseOffice, SetUnitOffice
from tst.sim.geo.cities import home_region
from tst.sim.geo.formulas import city_market_mid_cents
from tst.sim.hiring.models import PersonState
from tst.sim.hiring.phases import monthly_costs
from tst.sim.org.rules import org_view
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.products.models import SELLING
from tst.sim.products.team import product_team
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_employment, with_person, with_person_state

SEEDS: Final = tuple(range(1, 11))
TURNS: Final = 120
FIRST_REGION: Final = ("europe", "london")  # at Series A
SECOND_REGION: Final = ("east_asia", "tokyo")  # at stage 3
EXPANSION_SEATS: Final = 25
TEAM: Final = 30
TEAM_ROLE: Final = "software_engineer"
TEAM_LEVEL: Final = "mid"
TEAM_SEATS: Final = 50


# --- Target 2 ---------------------------------------------------------------------------------


def expand(game: Game) -> None:
    """Launch every live product in Europe after the Series A and in East Asia at stage 3,
    leasing a small office in each region for local presence (script only)."""
    steps = []
    if "a" in closed_series(game):
        steps.append(FIRST_REGION)
    if game.state.player.stage >= 3:  # tunable-exempt: 19.8 target 2's "at stage 3"
        steps.append(SECOND_REGION)
    data = game.loaded.game_data
    for region, city in steps:
        if not any(data.city(o.city).region == region for o in game.state.company_offices(PLAYER)):
            game.act(LeaseOffice(game.founder_id, city, EXPANSION_SEATS))
        for product in game.state.company_products(PLAYER):
            if product.status == "live" and game.state.product_region(product.id, region) is None:
                game.act(LaunchInRegion(game.founder_id, product.id, region))


def expansion_arm(seed: int) -> ArmResult:
    abroad = start_game(_loaded("data"), seed, SCENARIO)
    home = start_game(_loaded("data"), seed, SCENARIO)
    for game, grow in ((abroad, True), (home, False)):
        for _ in range(TURNS):
            if game.state.ended:
                break
            blitzscale(game)
            if grow:
                expand(game)
            game.turn()
    arr = [g.snapshots[-1].arr_cents if not g.state.ended else 0 for g in (abroad, home)]
    return ArmResult(seed, None, arr[0], arr[1])


def run_expansion(seeds: tuple[int, ...] = SEEDS, jobs: int = 1) -> list[ArmResult]:
    if jobs <= 1:
        return [expansion_arm(s) for s in seeds]
    with ProcessPoolExecutor(jobs) as pool:
        return list(pool.map(expansion_arm, seeds))


# --- Target 3 ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TeamCost:
    sf_cents: int
    bangalore_cents: int
    split_factor: float  # the cross-region factor of a product built in both cities

    @property
    def saving(self) -> float:
        return 1 - self.bangalore_cents / self.sf_cents


def _team_in(game: Game, city: str, first_id: int) -> GameState:
    """`game`'s state with TEAM engineers at the city's market rate in a team leased there."""
    data, balance = game.loaded.game_data, game.loaded.balance
    game.act(CreateUnit(game.founder_id, "team", f"Team {city}"))
    unit = max(game.state.active_units(PLAYER), key=lambda u: u.id)
    game.act(LeaseOffice(game.founder_id, city, TEAM_SEATS))
    office = max(game.state.company_offices(PLAYER), key=lambda o: o.id)
    game.act(SetUnitOffice(game.founder_id, unit.id, office.id))
    state = game.state
    band = data.role(TEAM_ROLE).salary_band_mid_cents[TEAM_LEVEL]
    pay = city_market_mid_cents(band, data.city(city))
    for offset in range(TEAM):
        pid = first_id + offset
        gen = RngFactory(pid).stream(0, "misc", pid)
        person = replace(
            generate_person(
                gen, data, balance, 0, data.role(TEAM_ROLE), TEAM_LEVEL, "north_america",
                person_id=pid,
            ),
            city=city,
        )
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(
                id=pid,
                person_id=pid,
                company_id=PLAYER,
                role=TEAM_ROLE,
                level=TEAM_LEVEL,
                salary_cents=pay,
                equity_bp=0,
                start_turn=0,
                end_turn=None,
                status="active",
                unit_id=unit.id,
            ),
        )
        state = with_person_state(state, PersonState(pid, morale=balance.morale.new_hire))
    return state


def _cost(game: Game, state: GameState, base: GameState) -> int:
    loaded = game.loaded
    total = sum(a for _, _, a in monthly_costs(state, PLAYER, loaded.balance, loaded.game_data))
    before = sum(a for _, _, a in monthly_costs(base, PLAYER, loaded.balance, loaded.game_data))
    return total - before


def team_cost(seed: int = 1) -> TeamCost:
    loaded = _loaded("data")
    base_game = start_game(loaded, seed, SCENARIO)
    base = base_game.state
    sf = Game(loaded, base, dict(base_game.balances))
    sf_state = _team_in(sf, "san_francisco", 1_000)
    blr = Game(loaded, base, dict(base_game.balances))
    blr_state = _team_in(blr, "bangalore", 1_000)
    # Both teams on one product: half the engineers in each city.
    both = Game(loaded, base, dict(base_game.balances))
    half = _team_in(both, "san_francisco", 1_000)
    both.state = half
    split = _team_in(both, "bangalore", 2_000)
    factor = 1.0
    data = loaded.game_data
    split_game = Game(loaded, split, dict(both.balances))
    pid = split_game.state.next_ids.product
    split_game.act(CreateProduct(split_game.founder_id, "Split", "b2b_saas", ("smb",)))
    for unit in split_game.state.active_units(PLAYER):
        split_game.act(AssignUnit(split_game.founder_id, pid, unit.id))
    product = split_game.state.product(pid)
    if product is not None:
        s = split_game.state
        team = product_team(
            s, org_view(s, PLAYER), product, data.category("b2b_saas"), loaded.balance, data
        )
        factor = team.region_factor
    return TeamCost(
        sf_cents=_cost(sf, sf_state, base),
        bangalore_cents=_cost(blr, blr_state, base),
        split_factor=factor,
    )


# --- Target 5 ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Spread:
    seed: int
    covered: int  # (region, category) pairs with a live rival product
    total: int
    missing: tuple[tuple[str, str], ...]


def coverage(state: GameState, game: Game) -> Spread:
    data, balance = game.loaded.game_data, game.loaded.balance
    home = home_region(state, balance, data)
    have: set[tuple[str, str]] = set()
    for product in state.products:
        company = state.company(product.company_id)
        if company.is_player or company.failed_turn is not None or product.status not in SELLING:
            continue
        if product.status != "live":
            continue
        if state.segments_of(product.id):
            have.add((home, product.category))
        for launch in state.regions_of(product.id):
            if launch.live(state.turn):
                have.add((launch.region, product.category))
    wanted = [(r, c.key) for r in data.region_keys for c in data.categories]
    missing = tuple(w for w in wanted if w not in have)
    return Spread(game.state.save_meta.master_seed, len(wanted) - len(missing), len(wanted), missing)


def spread_arm(seed: int) -> Spread:
    game = start_game(_loaded("data"), seed, SCENARIO)
    for _ in range(TURNS):
        if game.state.ended:
            break
        do_nothing(game)
        game.turn()
    return coverage(game.state, game)


def run_spread(seeds: tuple[int, ...] = SEEDS, jobs: int = 1) -> list[Spread]:
    if jobs <= 1:
        return [spread_arm(s) for s in seeds]
    with ProcessPoolExecutor(jobs) as pool:
        return list(pool.map(spread_arm, seeds))


def expansion_ratio(results: list[ArmResult]) -> float:
    return ratio(results)


def median_arr(results: list[ArmResult]) -> tuple[float, float]:
    used = [r for r in results if r.arr_a > 0 and r.arr_b > 0]
    if not used:
        return 0.0, 0.0
    return median(r.arr_a for r in used), median(r.arr_b for r in used)
