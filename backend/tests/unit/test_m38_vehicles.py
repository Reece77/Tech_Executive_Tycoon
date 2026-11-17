"""M38 sub-tasks 2-6 (formulas.md 49): a car's range and bill of materials, autonomy levels and
approvals, subsidies' sourcing rules, tariffs keeping car makers out, the seeded S-curve and
learning curve, and seeded autonomy incidents."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.products.models import Product, ProductSegment
from tst.sim.research.models import ResearchLead
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_product, with_product_segment, with_research_lead
from tst.sim.vehicles import autonomy, demand, rivals, subsidies
from tst.sim.vehicles import spec as vs
from tst.sim.vehicles.models import VehicleSpec

PLAYER = 1


def _car(state: GameState, turn: int, spec: VehicleSpec | None = None) -> tuple[GameState, int]:
    state = replace(state, turn=turn)
    pid, ids = state.next_ids.take("product")
    p = Product(
        id=pid,
        company_id=PLAYER,
        category="vehicles",
        name="Car",
        status="live",
        quality=60.0,
        feature_points=100.0,
        brand=40.0,
        marketing_budget_cents=0,
        created_turn=turn,
        launched_turn=turn,
    )
    state = replace(with_product(state, p), next_ids=ids)
    state = with_product_segment(state, ProductSegment(pid, "consumer", 3_000_000, 1000.0))
    s = spec or VehicleSpec(pid, 60.0, "nmc", 150.0, "l2", "licensed", "catl")
    state = replace(state, vehicle_specs=(replace(s, product_id=pid),))
    return state, pid


def test_range_and_points(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    spec = VehicleSpec(1, 60.0, "nmc", 150.0, "l2", "licensed", "catl")
    t = ym_to_turn(2024, 7)
    # 60 kWh x 0.92 usable x 6.0 km a kWh (2024) x NMC's 1.0
    assert vs.range_km(spec, t, b, d) == pytest.approx(60 * 0.92 * 6.0, rel=1e-3)
    lfp = replace(spec, chemistry="lfp")
    assert vs.range_km(lfp, t, b, d) < vs.range_km(spec, t, b, d)
    longer = replace(spec, pack_kwh=120.0)
    assert vs.range_points(longer, t, b, d) > vs.range_points(spec, t, b, d)
    assert vs.range_points(longer, t, b, d) <= b.vehicles.spec.range_cap


def test_bill_of_materials_by_line(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, pid = _car(fresh_game(loaded), ym_to_turn(2024, 7))
    p = state.product(pid)
    assert p is not None
    cost = vs.unit_cost(state, p, b, d)
    assert cost.total == pytest.approx(
        cost.cells + cost.integration + cost.drive + cost.chips + cost.body
    )
    # NMC from CATL: the market's cell price x 1.18 x 0.92 a kWh
    from tst.sim.vehicles import cells

    market = cells.market_cents(state, b, d)
    assert cost.cells == pytest.approx(60 * market * 1.18 * 0.92)
    lfp_state = replace(
        state, vehicle_specs=(VehicleSpec(pid, 60.0, "lfp", 150.0, "l2", "licensed", "catl"),)
    )
    assert vs.unit_cost(lfp_state, p, b, d).cells < cost.cells


def test_autonomy_needs_lead_and_approval(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    spec = VehicleSpec(0, 60.0, "nmc", 150.0, "l3", "own", "catl")
    state, pid = _car(fresh_game(loaded), ym_to_turn(2020, 1), spec)
    p = state.product(pid)
    assert p is not None
    assert vs.capable_level(state, vs.spec_of(state, p, d), PLAYER, b) == "l2"
    state = with_research_lead(state, ResearchLead(PLAYER, b.vehicles.domain, 30.0))
    # L3 needs an AI model of quality 65 too: L2+ is the most it reaches without one
    assert vs.capable_level(state, vs.spec_of(state, p, d), PLAYER, b) == "l2_plus"
    # North America approved L2+ in September 2017 (Super Cruise); L3 only from January 2023
    assert vs.level_in(state, p, "north_america", b, d) == "l2_plus"
    assert vs.level_in(state, p, "africa", b, d) == "l2"
    assert not vs.approved(state, "north_america", "l3", b, d)
    assert vs.approved(replace(state, turn=ym_to_turn(2023, 1)), "north_america", "l3", b, d)


def test_us_credit_sourcing_rules(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, pid = _car(fresh_game(loaded), ym_to_turn(2024, 3))
    p = state.product(pid)
    assert p is not None
    us = next(s for s in d.vehicles.subsidies if s.key == "us_30d")  # type: ignore[union-attr]
    failed = subsidies.rules_failed(state, p, us, 3_000_000, b, d)
    assert "IRA: no battery components from a foreign entity of concern" in failed
    korean = replace(
        state, vehicle_specs=(VehicleSpec(pid, 60.0, "nmc", 150.0, "l2", "licensed", "lges"),)
    )
    korean = replace(
        korean,
        vehicle_specs=(replace(korean.vehicle_specs[0], origin="us"),),
    )
    assert subsidies.rules_failed(korean, p, us, 3_000_000, b, d) == ()
    # before the 2024 rule a Chinese cell was fine; after September 2025 there is no credit
    early = replace(state, turn=ym_to_turn(2021, 1))
    assert subsidies.rules_failed(early, p, us, 3_000_000, b, d) == ()
    assert subsidies.schemes_in(replace(state, turn=ym_to_turn(2025, 11)), "north_america", d) == []
    # an eligible car's price buyers weigh falls by the credit x the US share of the region
    cut = subsidies.product_cut(korean, p, "north_america", 3_000_000, b, d)
    assert cut == pytest.approx(us.amount_at(korean.turn) * 0.88)


def test_the_us_tariff_keeps_chinese_car_makers_out(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = fresh_game(loaded)
    byd = next(c for c in state.companies if c.name == "BYD")
    tesla = next(c for c in state.companies if c.name == "Tesla")
    after = replace(state, turn=ym_to_turn(2026, 6))
    before = replace(state, turn=ym_to_turn(2023, 6))
    assert rivals.blocked_region(after, byd, "north_america", b, d)
    assert not rivals.blocked_region(before, byd, "north_america", b, d)
    assert not rivals.blocked_region(after, tesla, "north_america", b, d)


def test_s_curve_is_seeded_and_rises(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=b.vehicles.start_turn - 1)
    a = demand.world_month(state, RngFactory(5), b, d)
    again = demand.world_month(state, RngFactory(5), b, d)
    other = demand.world_month(state, RngFactory(6), b, d)
    assert a.vehicle_world == again.vehicle_world
    assert a.vehicle_world.k != other.vehicle_world.k
    k = dict(a.vehicle_world.k)
    assert all(b.vehicles.s_curve.k.lo <= x <= b.vehicles.s_curve.k.hi for x in k.values())
    s = replace(a, turn=b.vehicles.start_turn)
    stepped = demand.world_month(s, RngFactory(5), b, d)
    for region, lg in a.vehicle_world.logit:
        assert stepped.vehicle_world.logit_of(region) > lg  # type: ignore[operator]
    assert stepped.vehicle_world.cumulative_gwh > a.vehicle_world.cumulative_gwh


def test_learning_curve_falls_with_cumulative_cells(loaded: LoadedData) -> None:
    from tst.sim.vehicles import cells

    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=b.vehicles.start_turn - 1)
    state = demand.world_month(state, RngFactory(5), b, d)
    state = replace(state, turn=b.vehicles.start_turn)
    w = state.vehicle_world
    base = cells.learning_level(state, b, d)
    doubled = replace(state, vehicle_world=replace(w, cumulative_gwh=w.base_cumulative_gwh * 2))
    lower = cells.learning_level(doubled, b, d)
    assert base is not None and lower is not None and lower < base
    rate = w.learning_rate
    assert rate is not None
    m = b.vehicles.learning.metals_share
    assert lower / base == pytest.approx((1 - m) * (1 - rate) + m, rel=1e-3)


def test_incidents_are_seeded_and_recall(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    spec = VehicleSpec(0, 60.0, "nmc", 150.0, "l4", "own", "catl")
    state, pid = _car(fresh_game(loaded), ym_to_turn(2024, 1), spec)
    state = with_research_lead(state, ResearchLead(PLAYER, b.vehicles.domain, 60.0))
    ai = Product(
        id=state.next_ids.product,
        company_id=PLAYER,
        category="ai_models",
        name="Brain",
        status="live",
        quality=90.0,
        feature_points=10.0,
        brand=10.0,
        marketing_budget_cents=0,
        created_turn=0,
    )
    state = with_product(state, ai)
    seg = state.segments_of(pid)[0]
    state = with_product_segment(state, replace(seg, customers=2_000_000.0))
    runs = [autonomy.incidents_month(state, RngFactory(s), b, d) for s in (1, 1, 2)]
    assert runs[0][0].incidents == runs[1][0].incidents  # seeded
    hits = [r for r in runs if r[0].incidents]
    for st, entries, logs in hits:
        inc = st.incidents[-1]
        assert inc.level == "l4" and inc.region == "north_america"
        assert inc.cost_cents == round(2_000_000 * b.vehicles.incident.recall_cents)
        assert vs.suspended(st, PLAYER, "north_america", "l4")
        assert all(sum(x.amount for x in e.lines) == 0 for e in entries)
        assert logs
