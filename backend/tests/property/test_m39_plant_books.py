"""M39 sub-task 2 property test (formulas.md 53.1): plant books balance with robots installed. For
any plant kind, size, region, robots (own or bought), months and units run: every ledger entry
balances, the robots' cumulative depreciation never passes their capex, the saving a unit run is
between 0 and the plant's line labour, and the automation level stays within [0, max_share]. A
robotaxi zone's month balances too, for any fleet, price and city."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import tst.sim.actions  # noqa: F401  (robotics.actions is imported through the actions package)
from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities.models import Facility
from tst.sim.ledger import LedgerBalances
from tst.sim.rng import RngFactory
from tst.sim.robotics import automation
from tst.sim.robotics import robotaxi as rt
from tst.sim.robotics.actions import InstallRobots, install_robots
from tst.sim.robotics.models import Depot, Zone
from tst.sim.state import with_facility

PLAYER = 1
RICH: LedgerBalances = {(PLAYER, "1000_cash"): 10**15}
EPS = 1e-6


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    kind=st.sampled_from(["assembly_plant", "vehicle_plant"]),
    region=st.sampled_from(
        ["north_america", "europe", "east_asia", "south_southeast_asia", "africa"]
    ),
    size_index=st.integers(min_value=0, max_value=3),
    share=st.floats(min_value=0.01, max_value=1.0),
    months=st.integers(min_value=1, max_value=30),
    run=st.floats(min_value=0, max_value=1.0),
    year=st.integers(min_value=2012, max_value=2039),
)
def test_plant_books_balance(
    loaded: LoadedData,
    kind: str,
    region: str,
    size_index: int,
    share: float,
    months: int,
    run: float,
    year: int,
) -> None:
    b, d = loaded.balance, loaded.game_data
    sizes = b.facility.kinds[kind].sizes or b.facility.sizes
    cap = sizes[min(size_index, len(sizes) - 1)]
    state = replace(fresh_game(loaded), turn=ym_to_turn(year, 1))
    f = Facility(
        id=9001,
        company_id=PLAYER,
        kind=kind,
        region=region,
        capacity=cap,
        on_time=cap,
        ordered_turn=0,
        ready_turn=0,
        late_turn=0,
        capex_cents=cap * 30_000,
        input_index=1.0,
        capex_paid_cents=cap * 30_000,
        status="live",
        yield_rate=0.9,
    )
    state = with_facility(state, f)
    most = automation.robots_for(f, b.robotics.automation.max_share, b)
    robots = max(1, min(b.robotics.automation.max_robots, round(most * share)))
    founder = state.founder_of(PLAYER)
    assert founder is not None
    out = install_robots(state, InstallRobots(founder.id, f.id, robots), b, d, RICH)
    entries = list(out.entries)
    state = out.state
    labour = b.facility.kinds[kind].variable_cents * b.robotics.automation.labour_share[kind]
    for _ in range(months):
        state = automation.production_month(state, b, d)
        s = automation.unit_saving_cents(state, f.id)
        assert -EPS <= s <= labour + EPS
        plant = state.facility(f.id)
        assert plant is not None
        assert plant.yield_rate <= 0.995 + EPS
        state = with_facility(state, replace(plant, run_units=cap * run))
        state, more = automation.after_sales(state, b, d)
        entries += more
        state = replace(state, turn=state.turn + 1)
    for e in entries:
        assert sum(line.amount for line in e.lines) == 0
    a = state.plant_automation(f.id)
    assert a is not None
    assert 0 <= a.depreciated_cents <= a.capex_cents
    assert a.month is not None and 0 <= a.month.level <= b.robotics.automation.max_share + EPS


@settings(
    max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    cars=st.integers(min_value=1, max_value=500),
    price=st.integers(min_value=0, max_value=6000),
    city=st.sampled_from(["phoenix", "san_francisco", "wuhan", "london"]),
    size=st.sampled_from(["small", "medium", "large"]),
    depot=st.sampled_from([50, 100, 500]),
    seed=st.integers(min_value=1, max_value=1000),
)
def test_zone_month_balances(
    loaded: LoadedData, cars: int, price: int, city: str, size: str, depot: int, seed: int
) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2028, 5))
    service = max(p.id for p in state.products)
    zone = Zone(
        id=1,
        product_id=service,
        company_id=PLAYER,
        city=city,
        size=size,  # type: ignore[arg-type]
        status="active",
        applied_turn=state.turn - 10,
        approved_turn=state.turn - 2,
        cars=cars,
        capex_cents=cars * 9_000_000,
        price_cents=price,
    )
    region = rt.city(d, city).region
    dep = Facility(
        id=9100,
        company_id=PLAYER,
        kind="depot",
        region=region,
        capacity=depot,
        on_time=depot,
        ordered_turn=0,
        ready_turn=0,
        late_turn=0,
        capex_cents=1,
        input_index=1.0,
        status="live",
    )
    state = replace(with_facility(state, dep), zones=(zone,), depots=(Depot(dep.id, PLAYER, city),))
    out, entries, _ = rt.zones_month(state, RngFactory(seed), b, d)
    for e in entries:
        assert sum(line.amount for line in e.lines) == 0
    z = out.zones[0]
    assert z.month is not None
    assert 0 <= z.month.utilisation <= 1 + EPS
    assert z.depreciated_cents <= z.capex_cents
    assert z.month.rides <= min(cars, depot) * b.robotics.robotaxi.max_rides_per_day * 31
