"""M39's balance targets (docs/formulas.md 53.4), printed by tools/m39_targets.py.

Each seed's world is played by the engine from January 2010 to December 2025 with the player's
company doing nothing (so history holds), then on to December 2039; the targets read it:

2. **Automation pays where labour is dear:** in the played world's January 2030, a 2,000-car-a-
   month vehicle plant in North America and the same plant in South and Southeast Asia, each at
   the target automation level (robotics.automation.target_level), against the same plant
   without robots: the conversion cost a unit at full use (line labour, fixed cost, the plant's
   depreciation, the robots' depreciation and service: tst.sim.robotics.automation).
3. **Humanoids follow their era:** robotics revenue is the industrial and humanoid makers'
   booked revenue (each sells only its robots); the humanoid share of it in every year before
   the humanoid era arrives, and its largest yearly share within 8 years of the arrival (to
   December 2039 when the era comes after 2031).
4. **Robotaxis are a utilisation business:** from January 2027 the player's company gets L4 (an
   autonomy lead of 60 and an AI model of quality 90), a robotaxi service and a large San
   Francisco zone, active, with a 300-car depot; one run with 40 bought cars and one with 300,
   24 months each. Every month above `robotics.robotaxi.breakeven_rides` rides a car a day must
   earn a positive contribution; then in the 40-car run a serious incident in month 13 suspends
   the zone, and its revenue during the suspension against the 3 months before must fall by at
   least 30%.
5. **Turn time:** the mean wall-clock time of a turn from 2026 to 2035 on these worlds (the guards
   themselves are M30's `make check-timing`).
"""

from __future__ import annotations

import os
import pickle
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path
from statistics import median
from typing import Final

import tst.sim.actions  # noqa: F401  (robotics.actions is imported through the actions package)
from tst.balance.game import PLAYER, Game, start_game
from tst.loader import LoadedData, load_all
from tst.sim.calendar import turn_to_ym, ym_to_turn
from tst.sim.facilities.models import Facility
from tst.sim.ledger import CASH
from tst.sim.products.models import Product
from tst.sim.research.models import ResearchLead
from tst.sim.robotics import automation
from tst.sim.robotics import robotaxi as rt
from tst.sim.robotics.data import era_turn, file
from tst.sim.robotics.models import Depot, Zone
from tst.sim.state import GameState, with_company, with_facility, with_product, with_research_lead

SEEDS: Final = tuple(range(1, 11))
DATA: Final = Path(__file__).resolve().parents[2] / "data"
RICH: Final = 10**13
START: Final = 192  # January 2026
TAXI: Final = ym_to_turn(2027, 1)
YEAR_2030: Final = ym_to_turn(2030, 1)
END: Final = ym_to_turn(2039, 12)
PLANT_CARS: Final = 2_000
ERA_YEARS: Final = 8
HUMANOID_SHARE: Final = 0.20  # 53.4 target 3: at least this within 8 years
BEFORE_SHARE: Final = 0.01  # and under this before the era
TAXI_MONTHS: Final = 24
FLEETS: Final = (40, 300)
INCIDENT_MONTH: Final = 12
SUSPENSION_CUT: Final = 0.30
DEAR, CHEAP = "north_america", "south_southeast_asia"
TIMING_END: Final = ym_to_turn(2035, 12)


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


@cache
def _world_bytes(seed: int) -> bytes:
    """The seed's world to December 2025, the player doing nothing (history holds)."""
    g = start_game(loaded(), seed, "funded_spinout")
    g.balances[(PLAYER, CASH)] = g.balances.get((PLAYER, CASH), 0) + RICH
    while g.state.turn < START:
        g.turn()
    return pickle.dumps((g.state, g.balances))


def world(seed: int) -> Game:
    state, balances = pickle.loads(_world_bytes(seed))
    g = Game(loaded(), state, balances)
    g.state = with_company(g.state, replace(g.state.player, stage=4))
    return g


def _plant(state: GameState, region: str) -> Facility:
    return Facility(
        id=10**6,
        company_id=PLAYER,
        kind="vehicle_plant",
        region=region,
        capacity=PLANT_CARS,
        on_time=PLANT_CARS,
        ordered_turn=state.turn,
        ready_turn=state.turn,
        late_turn=state.turn,
        capex_cents=PLANT_CARS * 6_000_000,
        input_index=1.0,
        capex_paid_cents=PLANT_CARS * 6_000_000,
        status="live",
    )


def _total(report: dict[str, float]) -> float:
    return report["labour"] + report["fixed"] + report["depreciation"] + report["robots"]


def automation_cut(state: GameState, region: str) -> float:
    """Target 2: 1 - the conversion cost a unit at the target level over the cost without."""
    b, d = loaded().balance, loaded().game_data
    f = _plant(state, region)
    robots = automation.robots_for(f, b.robotics.automation.target_level, b)
    without = _total(automation.unit_cost_report(state, f, 0, b, d))
    with_ = _total(automation.unit_cost_report(state, f, robots, b, d))
    return 1 - with_ / without


def _revenue(g: Game, names: set[str]) -> int:
    ids = {c.id for c in g.state.companies if c.name in names}
    return -sum(v for (cid, acct), v in g.balances.items() if cid in ids and acct.startswith("4"))


def _product(state: GameState, category: str, name: str, quality: float) -> tuple[GameState, int]:
    pid, ids = state.next_ids.take("product")
    p = Product(
        id=pid,
        company_id=PLAYER,
        category=category,
        name=name,
        status="live",
        quality=quality,
        feature_points=500.0,
        brand=50.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
    )
    return replace(with_product(state, p), next_ids=ids), pid


def taxi_run(g: Game, cars: int, incident: bool) -> list[tuple[float, int, int]]:
    """Target 4: (rides a car a day, contribution, revenue) for each month of a 24-month run."""
    b = loaded().balance
    s = g.state
    s = with_research_lead(s, ResearchLead(PLAYER, b.vehicles.domain, 60.0))
    s, _ = _product(s, "ai_models", "Driver", 90.0)
    s, ride = _product(s, "mobility", "Ride", 60.0)
    depot = replace(_plant(s, "north_america"), id=10**6 + 1, kind="depot", capacity=300)
    s = with_facility(s, depot)
    zone = Zone(
        id=1,
        product_id=ride,
        company_id=PLAYER,
        city="san_francisco",
        size="large",
        status="active",
        applied_turn=s.turn - 9,
        approved_turn=s.turn,
        cars=cars,
        capex_cents=round(
            cars
            * rt.car_cents_for_zone(s, Zone(1, 0, 0, "", "large", "", 0), b, loaded().game_data)
        ),
    )
    g.state = replace(s, zones=(zone,), depots=(Depot(depot.id, PLAYER, "san_francisco"),))
    out = []
    days = b.robotics.robotaxi.days_per_month
    for month in range(TAXI_MONTHS):
        if incident and month == INCIDENT_MONTH:
            z = g.state.zones[0]
            state, z, _, _ = rt._incident(g.state, z, True, "Ride", b)
            g.state = replace(state, zones=(z,))
        g.turn()
        z = g.state.zones[0]
        m = z.month
        if m is None:
            out.append((0.0, 0, 0))
        else:
            out.append((m.rides / max(1, m.cars) / days, m.contribution_cents, m.revenue_cents))
    return out


@dataclass(frozen=True, slots=True)
class SeedRun:
    seed: int
    cut_dear: float
    cut_cheap: float
    era_turn: int | None
    before_max: float  # humanoid share of robotics revenue, the most in a year before the era
    after_max: float  # the most within 8 years of it
    above_months: int  # months above break-even
    above_positive: int  # of them, with a positive contribution
    suspension_cut: float
    turn_seconds: float


def run_seed(seed: int) -> SeedRun:
    g = world(seed)
    d = loaded().game_data
    f = file(d)
    industrial = {m.company for m in f.makers}
    humanoid = {m.company for m in f.humanoids.makers}
    year_rev: dict[int, tuple[int, int]] = {}
    last = (_revenue(g, industrial), _revenue(g, humanoid))
    cut_dear = cut_cheap = 0.0
    taxi: Game | None = None
    times: list[float] = []
    while g.state.turn <= END:
        if g.state.turn == YEAR_2030:
            cut_dear, cut_cheap = automation_cut(g.state, DEAR), automation_cut(g.state, CHEAP)
        if g.state.turn == TAXI:
            taxi = Game(loaded(), g.state, dict(g.balances))
        t0 = time.perf_counter()
        g.turn()
        if g.state.turn - 1 <= TIMING_END:
            times.append(time.perf_counter() - t0)
        if turn_to_ym(g.state.turn - 1)[1] == 12:
            now = (_revenue(g, industrial), _revenue(g, humanoid))
            year_rev[turn_to_ym(g.state.turn - 1)[0]] = (now[0] - last[0], now[1] - last[1])
            last = now
    era = era_turn(g.state, d)
    era_year = turn_to_ym(era)[0] if era is not None else None
    before = after = 0.0
    for year, (ind, hum) in sorted(year_rev.items()):
        share = hum / (ind + hum) if ind + hum > 0 else 0.0
        if era_year is None or year < era_year:
            before = max(before, share)
        elif year <= era_year + ERA_YEARS:
            after = max(after, share)
    above = positive = 0
    cut = 0.0
    assert taxi is not None
    for cars in FLEETS:
        branch = Game(loaded(), taxi.state, dict(taxi.balances))
        months = taxi_run(branch, cars, incident=cars == FLEETS[0])
        for i, (rides_day, contribution, _) in enumerate(months):
            if cars == FLEETS[0] and i >= INCIDENT_MONTH:
                continue
            if rides_day > loaded().balance.robotics.robotaxi.breakeven_rides:
                above += 1
                positive += contribution > 0
        if cars == FLEETS[0]:
            before_rev = sum(r for _, _, r in months[INCIDENT_MONTH - 3 : INCIDENT_MONTH]) / 3
            span = loaded().balance.robotics.robotaxi.suspend_months
            during = months[INCIDENT_MONTH : INCIDENT_MONTH + span]
            during_rev = sum(r for _, _, r in during) / max(1, len(during))
            cut = 1 - during_rev / before_rev if before_rev > 0 else 0.0
    return SeedRun(
        seed=seed,
        cut_dear=cut_dear,
        cut_cheap=cut_cheap,
        era_turn=era,
        before_max=before,
        after_max=after,
        above_months=above,
        above_positive=positive,
        suspension_cut=cut,
        turn_seconds=sum(times) / len(times) if times else 0.0,
    )


@dataclass(frozen=True, slots=True)
class Results:
    runs: tuple[SeedRun, ...]


def run(seeds: Sequence[int] = SEEDS, jobs: int = os.cpu_count() or 1) -> Results:
    if jobs <= 1:
        return Results(tuple(run_seed(s) for s in seeds))
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        return Results(tuple(pool.map(run_seed, seeds)))


def report(r: Results) -> str:
    from tst.sim.calendar import format_turn

    lines = [
        "M39 balance targets (formulas.md 53.4), seeds " + ", ".join(str(x.seed) for x in r.runs)
    ]
    for x in r.runs:
        era = format_turn(x.era_turn) if x.era_turn is not None else "not by 2039"
        lines.append(
            f"  seed {x.seed}: automation cut NA {x.cut_dear:.1%}, SSEA {x.cut_cheap:.1%}; era"
            f" {era}, humanoid share before {x.before_max:.2%}, within 8 years {x.after_max:.1%};"
            f" robotaxi months above break-even {x.above_positive}/{x.above_months} positive,"
            f" suspension cut {x.suspension_cut:.0%}; {x.turn_seconds * 1000:.0f} ms a turn"
        )
    dear = median(x.cut_dear for x in r.runs)
    cheap = max(x.cut_cheap for x in r.runs)
    before = max(x.before_max for x in r.runs)
    after = median(x.after_max for x in r.runs)
    above = sum(x.above_months for x in r.runs)
    positive = sum(x.above_positive for x in r.runs)
    cut = min(x.suspension_cut for x in r.runs)
    ok4 = positive == above and above > 0 and cut >= SUSPENSION_CUT
    lines += [
        f"2. Automation pays where labour is dear: median cut {dear:.1%} in North America (>= 15%),"
        f" at most {cheap:.1%} in South and Southeast Asia (<= 5%):"
        f" {'met' if dear >= 0.15 and cheap <= 0.05 else 'MISSED'}",
        f"3. Humanoids follow their era: share before the era at most {before:.2%} (< 1%),"
        f" median within 8 years {after:.1%} (>= 20%):"
        f" {'met' if before < BEFORE_SHARE and after >= HUMANOID_SHARE else 'MISSED'}",
        f"4. Robotaxis are a utilisation business: {positive} of {above} months above break-even"
        f" positive; a suspension cuts revenue at least {cut:.0%} (>= 30%):"
        f" {'met' if ok4 else 'MISSED'}",
        f"5. Turn time: median {median(x.turn_seconds for x in r.runs) * 1000:.0f} ms a turn"
        " (2026-2035; the guards are make check-timing)",
    ]
    return "\n".join(lines)
