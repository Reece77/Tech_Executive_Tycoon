"""M39 sub-tasks 2-4 (formulas.md 53): plant automation's saving by region, humanoid capability,
demand and the actuators' learning curve, robotaxi zones (permits, rides, economics, seeded
incidents and suspensions), and the rival makers' hold on history."""

from __future__ import annotations

from dataclasses import replace

import pytest

import tst.sim.actions  # noqa: F401  (robotics.actions is imported through the actions package)
from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.errors import RoboticsRuleError
from tst.sim.facilities.models import Facility
from tst.sim.ledger import LedgerBalances
from tst.sim.products.models import Product
from tst.sim.research.models import EraArrival, ResearchLead
from tst.sim.rng import RngFactory
from tst.sim.robotics import automation, demand, humanoids, rivals
from tst.sim.robotics import robotaxi as rt
from tst.sim.robotics.actions import InstallRobots, OpenZone, install_robots, open_zone
from tst.sim.robotics.data import year_at
from tst.sim.robotics.models import HumanoidSpec, PlantAutomation, Zone
from tst.sim.state import (
    GameState,
    with_era_arrival,
    with_facility,
    with_product,
    with_research_lead,
)

PLAYER = 1
RICH: LedgerBalances = {(PLAYER, "1000_cash"): 10**14}


def _plant(state: GameState, region: str, kind: str = "vehicle_plant", cap: int = 2000) -> Facility:
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
        capex_cents=cap * 6_000_000,
        input_index=1.0,
        capex_paid_cents=cap * 6_000_000,
        status="live",
        yield_rate=0.95,
    )
    return f


def test_automation_pays_where_labour_is_dear(loaded: LoadedData) -> None:
    """53.4 target 2's shape: at the target level a North American plant's conversion cost a unit
    falls far more than a South and Southeast Asian one's (whose may even rise)."""
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2030, 6))
    level = b.robotics.automation.target_level
    out = {}
    for region in ("north_america", "south_southeast_asia"):
        f = _plant(state, region)
        robots = automation.robots_for(f, level, b)
        base = automation.unit_cost_report(state, f, 0, b, d)
        auto = automation.unit_cost_report(state, f, robots, b, d)
        total = lambda r: r["labour"] + r["fixed"] + r["depreciation"] + r["robots"]  # noqa: E731
        out[region] = 1 - total(auto) / total(base)
    assert out["north_america"] >= 0.15
    assert out["south_southeast_asia"] <= 0.05


def test_saving_never_exceeds_line_labour(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2030, 6))
    f = _plant(state, "north_america")
    full = automation.saving_cents(state, f, 1.0, b, d)
    assert full <= b.facility.kinds["vehicle_plant"].variable_cents + 1e-9
    assert automation.level_of(f, 10**9, b) == pytest.approx(b.robotics.automation.max_share)
    assert automation.level_of(f, 0, b) == 0.0


def test_install_robots_books_capex_and_reads_through_the_hook(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2027, 1))
    f = _plant(state, "north_america")
    state = with_facility(state, f)
    founder = state.founder_of(PLAYER)
    assert founder is not None
    out = install_robots(state, InstallRobots(founder.id, f.id, 100), b, d, RICH)
    (entry,) = out.entries
    assert sum(line.amount for line in entry.lines) == 0
    a = out.state.plant_automation(f.id)
    assert a is not None and a.robots == 100 and a.capex_cents > 0
    state = automation.production_month(out.state, b, d)
    assert automation.unit_saving_cents(state, f.id) > 0
    from tst.sim.hardware.production import plant_unit_cents

    assert plant_unit_cents(state, f, b) < b.facility.kinds["vehicle_plant"].variable_cents
    # a plant without robots reads exactly its variable cost
    other = replace(f, id=9002)
    assert plant_unit_cents(state, other, b) == b.facility.kinds["vehicle_plant"].variable_cents


def _humanoid(state: GameState, quality: float) -> tuple[GameState, Product]:
    pid, ids = state.next_ids.take("product")
    p = Product(
        id=pid,
        company_id=PLAYER,
        category="humanoid_robots",
        name="Helper",
        status="live",
        quality=quality,
        feature_points=100.0,
        brand=40.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
    )
    return replace(with_product(state, p), next_ids=ids), p


def test_humanoid_capability_and_actuators(loaded: LoadedData) -> None:
    b, _d = loaded.balance, loaded.game_data
    state, p = _humanoid(replace(fresh_game(loaded), turn=ym_to_turn(2031, 1)), 80.0)
    hb = b.robotics.humanoids
    licensed = humanoids.capability(state, p, b)
    w = hb.weights
    assert licensed == pytest.approx(
        w["hardware"] * 80 + w["ai"] * hb.licensed_ai_quality + w["chips"] * hb.bought_chip_quality
    )
    ai, ids = state.next_ids.take("product")
    model = replace(p, id=ai, category="ai_models", name="Model", quality=95.0)
    state = replace(with_product(state, model), next_ids=ids)
    state = replace(state, humanoid_specs=(HumanoidSpec(p.id, ai_product_id=ai),))
    assert humanoids.capability(state, p, b) > licensed
    # actuators: 1.0 at the base, a learning-rate cut a doubling
    assert humanoids.actuator_index(state, b) == pytest.approx(1.0)
    world = replace(state.robotics_world, actuator_units=hb.base_units)
    doubled = replace(state, robotics_world=world)
    assert humanoids.actuator_index(doubled, b) == pytest.approx(1 - hb.learning_rate)


def test_humanoid_market_is_closed_before_the_era(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2029, 6))
    assert demand.humanoid_addressable(state, "north_america", "logistics", b, d) == 0.0
    era = ym_to_turn(2030, 3)
    state = with_era_arrival(replace(state, turn=era), EraArrival("humanoid_robotics", era))
    rng = RngFactory(7)
    state = demand.world_month(state, rng, b, d)
    assert state.robotics_world.adoption
    assert state.robotics_world.home_turn is not None and state.robotics_world.home_turn > era
    assert demand.humanoid_addressable(state, "north_america", "logistics", b, d) > 0
    # homes open only from the seeded window
    assert demand.humanoid_addressable(state, "north_america", "consumer", b, d) == 0.0
    # adoption rises fastest where labour is dear
    state, _ = _humanoid(state, 75.0)
    for _ in range(36):
        state = demand.world_month(replace(state, turn=state.turn + 1), rng, b, d)
    na = demand.adoption_share(state, "north_america", b)
    ssea = demand.adoption_share(state, "south_southeast_asia", b)
    assert na > ssea > 0


def test_installations_history_and_seeded_growth(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    r = d.robotics
    assert r is not None
    state = replace(fresh_game(loaded), turn=ym_to_turn(2024, 7))
    got = demand.installations(state, "east_asia", b, d)
    t = year_at(state.turn)  # a year's point sits at its middle
    assert got == pytest.approx(r.region("east_asia").installed_at(t) * 1000, rel=1e-9)
    later = replace(state, turn=ym_to_turn(2027, 7))
    a = demand.world_month(replace(later, turn=b.robotics.start_turn - 1), RngFactory(1), b, d)
    a = demand.world_month(replace(a, turn=later.turn), RngFactory(1), b, d)
    again = demand.world_month(replace(later, turn=b.robotics.start_turn - 1), RngFactory(1), b, d)
    again = demand.world_month(replace(again, turn=later.turn), RngFactory(1), b, d)
    assert a.robotics_world.growth == again.robotics_world.growth  # seeded
    lo, hi = b.robotics.growth_after.lo, b.robotics.growth_after.hi
    assert all(lo <= g <= hi for _, _, g in a.robotics_world.growth)


def test_robot_makers_hold_on_history(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = fresh_game(loaded)
    fanuc = next(c for c in state.companies if c.name == "FANUC")
    optimus = next(c for c in state.companies if c.name == "Tesla Optimus")
    assert rivals.holds(state, fanuc, b, d)
    assert rivals.holds(state, optimus, b, d)
    later = replace(state, turn=b.robotics.start_turn)
    assert not rivals.holds(later, fanuc, b, d)
    assert rivals.holds(later, optimus, b, d)  # no era yet
    era = with_era_arrival(later, EraArrival("humanoid_robotics", later.turn))
    assert not rivals.holds(era, optimus, b, d)


def _l4(state: GameState, loaded: LoadedData) -> GameState:
    b = loaded.balance
    level = b.vehicles.levels["l4"]
    state = with_research_lead(state, ResearchLead(PLAYER, b.vehicles.domain, level.lead + 1))
    pid, ids = state.next_ids.take("product")
    model = Product(
        id=pid,
        company_id=PLAYER,
        category="ai_models",
        name="Driver",
        status="live",
        quality=level.ai_quality + 5,
        feature_points=100.0,
        brand=40.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
    )
    state = replace(with_product(state, model), next_ids=ids)
    sid, ids = state.next_ids.take("product")
    service = replace(model, id=sid, category="mobility", name="Ride", quality=60.0)
    return replace(with_product(state, service), next_ids=ids)


def test_zone_rules_and_breakeven(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2027, 1))
    founder = state.founder_of(PLAYER)
    assert founder is not None
    service = max(p.id for p in state.products)
    with pytest.raises(RoboticsRuleError):  # no L4 yet
        open_zone(state, OpenZone(founder.id, service, "phoenix", "small"), b, d)
    state = _l4(state, loaded)
    service = max(p.id for p in state.products if p.category == "mobility")
    out = open_zone(state, OpenZone(founder.id, service, "phoenix", "small"), b, d)
    (zone,) = out.state.zones
    assert zone.status == "applied" and zone.decision_turn is not None
    c = rt.city(d, "phoenix")
    car = 10_000_000
    be = rt.breakeven_rides(c, b, car)
    assert 0 < be < b.robotics.robotaxi.max_rides_per_day
    assert be == pytest.approx(b.robotics.robotaxi.breakeven_rides, rel=0.5)


def _active_zone(state: GameState, cars: int) -> GameState:
    service = max(p.id for p in state.products if p.category == "mobility")
    zone = Zone(
        id=1,
        product_id=service,
        company_id=PLAYER,
        city="san_francisco",
        size="large",
        status="active",
        applied_turn=state.turn - 6,
        approved_turn=state.turn - 1,
        cars=cars,
        capex_cents=cars * 10_000_000,
    )
    return replace(state, zones=(zone,))


def test_rides_economics_and_seeded_incidents(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _l4(replace(fresh_game(loaded), turn=ym_to_turn(2027, 3)), loaded)
    state = _active_zone(state, 100)
    rng = RngFactory(5)
    # no depot: no rides
    out, entries, _ = rt.zones_month(state, rng, b, d)
    assert out.zones[0].month is not None and out.zones[0].month.rides == 0
    from tst.sim.robotics.models import Depot

    depot = replace(_plant(state, "north_america", "depot", 100), id=9100)
    state = replace(with_facility(state, depot), depots=(Depot(depot.id, PLAYER, "san_francisco"),))
    out, entries, _logs = rt.zones_month(state, rng, b, d)
    month = out.zones[0].month
    assert month is not None and month.rides > 0
    assert 0 < month.utilisation <= 1
    for e in entries:
        assert sum(line.amount for line in e.lines) == 0
    again, entries2, _logs2 = rt.zones_month(state, RngFactory(5), b, d)
    assert again == out and entries2 == entries  # seeded
    # a suspended zone has no rides but its cars still cost money
    sus = replace(
        state, zones=(replace(state.zones[0], status="suspended", suspended_until=state.turn + 3),)
    )
    out3, _entries3, _ = rt.zones_month(sus, rng, b, d)
    m3 = out3.zones[0].month
    assert m3 is not None and m3.rides == 0 and m3.revenue_cents == 0 and m3.insurance_cents > 0


def test_serious_incident_suspends_and_queues_a_critical_event(loaded: LoadedData) -> None:
    b, _d = loaded.balance, loaded.game_data
    state = _l4(replace(fresh_game(loaded), turn=ym_to_turn(2027, 3)), loaded)
    state = _active_zone(state, 100)
    zone = state.zones[0]
    new_state, z, _entries, _logs = rt._incident(state, zone, True, "Ride in SF", b)
    assert (
        z.status == "suspended"
        and z.suspended_until == state.turn + b.robotics.robotaxi.suspend_months
    )
    assert any(q.template_id.startswith("robotaxi_") for q in new_state.queued)
    assert new_state.robo_incidents[-1].serious


def test_contribution_positive_above_breakeven(loaded: LoadedData) -> None:
    """53.4 target 4's first half on the formulas: at breakeven + 2 rides a car a day a car's
    month earns a positive contribution at the city's fare."""
    b, d = loaded.balance, loaded.game_data
    rb = b.robotics.robotaxi
    c = rt.city(d, "san_francisco")
    car = 10_000_000
    be = rt.breakeven_rides(c, b, car)
    for rides_day, sign in ((be + 2, 1), (max(0.0, be - 2), -1)):
        rides = rides_day * rb.days_per_month
        zone = Zone(1, 1, PLAYER, c.key, "large", "active", 0, cars=1, capex_cents=car)
        energy, cleaning, insurance, remote, _ = rt.zone_costs(zone, rides, c, b)
        dep = rt.car_month_depreciation(zone, b)
        contribution = rides * c.fare_cents - (energy + cleaning + insurance + remote + dep)
        assert contribution * sign > 0


def test_no_automation_no_change(loaded: LoadedData) -> None:
    """53.4 target 1: with no robots, zones or humanoids the robotics phases leave the state as
    it was apart from the markets' demand."""
    b, d = loaded.balance, loaded.game_data
    state = fresh_game(loaded)
    assert automation.production_month(state, b, d) is state
    s2, entries = automation.after_sales(state, b, d)
    assert s2 is state and entries == []
    s3, e3, l3 = rt.zones_month(state, RngFactory(1), b, d)
    assert s3 is state and e3 == [] and l3 == []
    assert PlantAutomation  # imported for the property test's shape


def test_incident_event_answers(loaded: LoadedData) -> None:
    """53.3's critical event: cooperating halves the suspension's months left at a cost;
    compensating restores brand; the event finds its zone by the month it is shown."""
    from tst.sim.events.models import GameEvent
    from tst.sim.robotics.events import robotics_step

    b, d = loaded.balance, loaded.game_data
    state = _l4(replace(fresh_game(loaded), turn=ym_to_turn(2027, 3)), loaded)
    state = _active_zone(state, 100)
    state, zone, _, _ = rt._incident(state, state.zones[0], True, "Ride in SF", b)
    state = replace(
        state,
        zones=(
            replace(
                state.zone(zone.id) or zone,
                status=zone.status,
                suspended_until=zone.suspended_until,
            ),
        ),
    )
    shown = replace(state, turn=state.turn + 1)
    event = GameEvent(
        1, PLAYER, shown.turn, "robotaxi_collision", "robotics", "critical", "robotics", 1.0
    )
    left = (zone.suspended_until or 0) - shown.turn
    out, entries, _ = robotics_step(shown, event, "cooperate", b, d)
    z = out.zone(zone.id)
    assert z is not None and z.event_turn is None
    assert z.suspended_until == shown.turn + round(left * b.robotics.incident_event.cooperate_share)
    assert entries and all(sum(x.amount for x in e.lines) == 0 for e in entries)
    service = shown.product(zone.product_id)
    assert service is not None
    out2, _, _ = robotics_step(shown, event, "compensate", b, d)
    after = out2.product(zone.product_id)
    assert after is not None and after.brand > service.brand
