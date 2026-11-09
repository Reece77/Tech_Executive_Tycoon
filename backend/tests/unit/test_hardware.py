"""M12b: unit-sale markets, bills of materials, contract manufacturing, assembly plants and
fabless chips (docs/formulas.md 26.1-26.3)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, with_employee, with_product
from tst.loader import LoadedData
from tst.sim.actions import (
    BuildFacility,
    SellPlantCapacity,
    SignManufacturingContract,
    SignWaferContract,
    apply_action,
)
from tst.sim.actions.products import launch_problems
from tst.sim.calendar import ym_to_turn
from tst.sim.chips import chips
from tst.sim.commodities import costs
from tst.sim.decisions import Decisions
from tst.sim.errors import FacilityRuleError, ProductRuleError
from tst.sim.facilities import formulas as ff
from tst.sim.facilities import goods, lifecycle
from tst.sim.facilities.models import Facility
from tst.sim.hardware import production
from tst.sim.hardware.models import ProductionContract
from tst.sim.hardware.phase import plant_yields
from tst.sim.hardware.supply import delivered_share
from tst.sim.ledger import CASH, COGS, GENERAL_ADMIN, REVENUE_SUBSCRIPTIONS, LedgerBalances
from tst.sim.people.generator import generate_person
from tst.sim.products import phases
from tst.sim.products.models import Product
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_employment, with_facility, with_production_contract
from tst.sim.turn import advance_turn

RICH: LedgerBalances = {(1, CASH): 10**13}
SHENZHEN = "shenzhen"


def _founder(state: GameState) -> int:
    founder = state.founder_of(1)
    assert founder is not None
    return founder.id


def _act(state: GameState, action: object, loaded: LoadedData) -> GameState:
    out = apply_action(
        state,
        action,  # type: ignore[arg-type]
        RngFactory(1),
        loaded.balance,
        loaded.game_data,
        RICH,
        seq=0,
    )
    return out.new_state


def _device(state: GameState, *, quality: float = 75.0, price: int = 40_000) -> GameState:
    return with_product(
        state,
        category="devices",
        prices={"consumer": price},
        quality=quality,
        brand=70.0,
        feature_points=10_000.0,
        name="Pebble Phone",
    )


def _contract(
    state: GameState,
    product_id: int,
    units: int,
    *,
    signed: int | None = None,
    kind: str = "assembly",
) -> GameState:
    cid, ids = state.next_ids.take("production_contract")
    turn = state.turn if signed is None else signed
    c = ProductionContract(
        id=cid,
        company_id=1,
        product_id=product_id,
        kind=kind,  # type: ignore[arg-type]
        supplier="foxconn" if kind == "assembly" else "tsmc",
        units=units,
        price_millicents=1_300_000 if kind == "assembly" else 900_000_000,
        signed_turn=turn,
        end_turn=turn + 23,
        city=SHENZHEN if kind == "assembly" else None,
    )
    return with_production_contract(replace(state, next_ids=ids), c)


def _pid(state: GameState, name: str) -> int:
    return next(p.id for p in state.products if p.name == name)


def _lines(entries: tuple, account: str, company: int = 1) -> int:  # type: ignore[type-arg]
    return sum(
        line.amount
        for e in entries
        if e.company_id == company
        for line in e.lines
        if line.account == account
    )


# --- Sub-task 2: unit-sale markets -----------------------------------------------------------


def test_subscriptions_have_no_plan(loaded: LoadedData) -> None:
    """A company that never enters hardware has no production plan, no rows and no cost of
    goods: its phase 5 is exactly as before (26, principle)."""
    state = with_product(fresh_game(loaded), customers={"smb": 100.0})
    assert production.build_plan(state, loaded.balance, loaded.game_data) is None
    out = phases.run_markets(state, RngFactory(4), loaded.balance, loaded.game_data)
    assert out.state.production == ()
    assert _lines(out.entries, COGS) == 0


def test_units_sell_once_and_are_capped(loaded: LoadedData) -> None:
    """A customer in play buys one unit; revenue is units x price, once; the capacity cap
    holds and the lost demand goes to a rival (26.1)."""
    data, balance = loaded.game_data, loaded.balance
    state = _device(fresh_game(loaded))
    pid = _pid(state, "Pebble Phone")
    state = _contract(state, pid, 1_000)
    out = phases.run_markets(state, RngFactory(4), balance, data)
    row = out.state.production_of(pid)
    assert row is not None
    assert row.units == pytest.approx(1_000)  # demand far above the cap
    assert row.lost_units > 0
    seg = out.state.product_segment(pid, "consumer")
    assert seg is not None and seg.customers == pytest.approx(1_000)
    assert _lines(out.entries, REVENUE_SUBSCRIPTIONS) == -(1_000 * 40_000)
    # BOM $180 x index 1, a bought SoC $40, the $13 fee: $233 a unit (26.7); M17 (33.2): the
    # BOM's index blends in its commodities at January 2010's spot (their index, not 1.0)
    index = costs.cost_index(out.state, "device_bom", data, balance)
    assert index != 1.0 and index == pytest.approx(1.0, abs=0.01)
    unit = 18_000 * index + 4_000 + 1_300
    assert _lines(out.entries, COGS) == pytest.approx(1_000 * unit, abs=2)
    assert row.cogs_cents == _lines(out.entries, COGS)
    # next month the same customers do not pay again: only new units book revenue
    nxt = replace(out.state, turn=out.state.turn + 1)
    out2 = phases.run_markets(nxt, RngFactory(4), balance, data)
    row2 = out2.state.production_of(pid)
    assert row2 is not None and row2.units == pytest.approx(1_000)


def test_lost_demand_goes_to_the_next_best(loaded: LoadedData) -> None:
    """Rivals win more with the player capped than without it."""
    data, balance = loaded.game_data, loaded.balance
    base = _device(fresh_game(loaded))
    pid = _pid(base, "Pebble Phone")
    capped = phases.run_markets(_contract(base, pid, 10), RngFactory(4), balance, data)
    free = phases.run_markets(_contract(base, pid, 10**6), RngFactory(4), balance, data)

    def rivals(s: GameState) -> float:
        return sum(
            seg.customers
            for p in s.products
            if p.category == "devices" and p.company_id != 1
            for seg in s.segments_of(p.id)
            if seg.segment == "consumer"
        )

    assert rivals(capped.state) > rivals(free.state)


def test_replacement_cycle_is_base_churn(loaded: LoadedData) -> None:
    data = loaded.game_data
    devices = data.category("devices")
    assert devices.market("consumer").replacement_months == 30
    from tst.sim.products import formulas as pf

    assert pf.unit_base_churn(devices, 0.06, "consumer") == pytest.approx(1 / 30)
    assert pf.unit_base_churn(devices, 0.03, "smb") == pytest.approx(1 / 40)
    assert pf.unit_base_churn(data.category("b2b_saas"), 0.03, "smb") == 0.03


def test_launch_needs_quality_and_a_source(loaded: LoadedData) -> None:
    """Quality >= 30 and a manufacturing source (26.1)."""
    state = with_product(
        fresh_game(loaded),
        category="devices",
        prices={"consumer": 40_000},
        status="in_development",
        quality=20.0,
        feature_points=10_000.0,
        name="Pebble Phone",
    )
    product = state.product(_pid(state, "Pebble Phone"))
    assert product is not None
    problems = launch_problems(state, product, loaded.balance, loaded.game_data)
    assert any("quality" in p for p in problems)
    assert any("manufacturing contract" in p for p in problems)
    state = _contract(state, product.id, 100)
    product = replace(product, quality=35.0)
    from tst.sim.state import with_product as put

    state = put(state, product)
    assert launch_problems(state, product, loaded.balance, loaded.game_data) == []


def test_fast_feature_expectations(loaded: LoadedData) -> None:
    data = loaded.game_data
    assert data.category("devices").features_per_month == 8
    assert data.category("servers").features_per_month == 8
    assert data.category("chips_ai_accelerator").features_per_month == 10


def test_quality_cap_uses_the_devices_domain(loaded: LoadedData) -> None:
    from tst.sim.research.levels import tech_factor
    from tst.sim.research.models import ResearchLead

    state = replace(fresh_game(loaded), research_leads=(ResearchLead(1, "devices", 20.0),))
    f = tech_factor(state, 1, "devices", loaded.balance, loaded.game_data)
    assert f.cap_mult == pytest.approx(1 + loaded.balance.rnd.cap_per_point * 20)
    chip = tech_factor(state, 1, "chips_mobile_soc", loaded.balance, loaded.game_data)
    assert chip.cap_mult == 1.0  # chips use chip design


# --- Sub-task 3: bills of materials and contract manufacturing ------------------------------


def test_sign_contract_action(loaded: LoadedData) -> None:
    state = _device(fresh_game(loaded))
    pid = _pid(state, "Pebble Phone")
    founder = _founder(state)
    state = _act(
        state, SignManufacturingContract(founder, pid, "foxconn", SHENZHEN, 5_000, 12), loaded
    )
    (c,) = state.production_contracts
    assert (c.units, c.price_cents, c.end_turn) == (5_000, 1_300.0, 11)
    elsewhere = _act(
        state,
        SignManufacturingContract(founder, pid, "pegatron", "san_francisco", 1_000, 24),
        loaded,
    )
    assert elsewhere.production_contracts[-1].price_cents == pytest.approx(1_300 * 1.03 * 1.3)
    with pytest.raises(FacilityRuleError):
        _act(state, SignManufacturingContract(founder, pid, "foxconn", SHENZHEN, 5_000, 36), loaded)
    b2b = with_product(fresh_game(loaded))
    with pytest.raises(ProductRuleError):
        _act(
            b2b,
            SignManufacturingContract(founder, b2b.products[-1].id, "foxconn", SHENZHEN, 1, 12),
            loaded,
        )


def test_take_or_pay_on_unused_volume(loaded: LoadedData) -> None:
    """50% of the fee on each unused unit of the month's volume (26.2)."""
    data, balance = loaded.game_data, loaded.balance
    state = _device(fresh_game(loaded))
    pid = _pid(state, "Pebble Phone")
    state = _contract(state, pid, 1_000)
    state, entries = production.settle(state, None, {}, balance, data)  # nothing sold
    assert _lines(tuple(entries), GENERAL_ADMIN) == round(1_000 * 1_300 * 0.5)
    (c,) = state.production_contracts
    assert c.charged_cents == 650_000 and c.used == 0 and c.delivered == 1_000


def test_shortage_allocation(loaded: LoadedData) -> None:
    """A contract signed before the 2021 shortage keeps 100%; one signed during it gets 70%
    (26.2)."""
    data = loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2021, 6))
    assert delivered_share(state, "device_bom", ym_to_turn(2020, 6), data) == 1.0
    assert delivered_share(state, "device_bom", ym_to_turn(2021, 2), data) == 0.70
    calm = replace(state, turn=ym_to_turn(2019, 6))
    assert delivered_share(calm, "device_bom", ym_to_turn(2019, 1), data) == 1.0


def test_bom_follows_the_index(loaded: LoadedData) -> None:
    state = _device(replace(fresh_game(loaded), turn=ym_to_turn(2022, 4)))
    product = state.product(_pid(state, "Pebble Phone"))
    assert product is not None
    bom = production.unit_bom_cents(state, product, loaded.balance, loaded.game_data)
    # the components index of April 2022 (26.2), blended with its commodities (M17, 33.2)
    assert goods.index_now(state, "device_bom", loaded.game_data) == pytest.approx(0.7978)
    mix = loaded.balance.commodity.mixes["device_bom"]
    spot = costs.mix_index(state, mix, loaded.game_data)
    assert bom == pytest.approx(18_000 * costs.apply_mix(0.7978, mix, spot), rel=1e-3)


# --- Sub-task 4: assembly plants -------------------------------------------------------------


def _plant(
    state: GameState, loaded: LoadedData, units: int, *, staff: int, skill: float
) -> GameState:
    """A paid, live, staffed plant in Shenzhen."""
    balance = loaded.balance
    kind = balance.facility.kinds["assembly_plant"]
    from tst.sim.actions.org import CreateUnit

    state = _act(state, CreateUnit(_founder(state), "team", "Plant crew"), loaded)
    unit = state.units[-1]
    for i in range(staff):
        person = generate_person(
            RngFactory(9).stream(0, "people_gen", 900 + i),
            loaded.game_data,
            balance,
            0,
            loaded.game_data.role("manufacturing_engineer"),
            "mid",
            "east_asia",
            person_id=900_000 + i,
        )
        person = replace(
            person,
            role="manufacturing_engineer",
            skills=person.skills.updated({"manufacturing": skill}),
        )
        state = with_employee(loaded, state, person, 7_000_000)
        emp = state.employment_of(person.id)
        assert emp is not None
        state = with_employment(state, replace(emp, unit_id=unit.id))
    capex = ff.capex_cents(units, kind.capex_per_unit_cents, 1.0)
    fid, ids = state.next_ids.take("facility")
    plant = Facility(
        id=fid,
        company_id=1,
        kind="assembly_plant",
        region="east_asia",
        capacity=units,
        on_time=units,
        ordered_turn=state.turn - kind.build_months,
        ready_turn=state.turn,
        late_turn=state.turn,
        capex_cents=capex,
        input_index=1.0,
        capex_paid_cents=capex,
        status="live",
        city=SHENZHEN,
        unit_id=unit.id,
    )
    return with_facility(replace(state, next_ids=ids), plant)


def test_plant_yield_is_seeded(loaded: LoadedData) -> None:
    """yield = 0.85 + 0.10 x skill / 20 with noise on stream manufacturing: the same seed
    gives the same yield, a different seed another, near the formula."""
    state = _plant(fresh_game(loaded), loaded, 5_000, staff=5, skill=14.0)
    a = plant_yields(state, RngFactory(7), loaded.balance).facilities[-1].yield_rate
    b = plant_yields(state, RngFactory(7), loaded.balance).facilities[-1].yield_rate
    c = plant_yields(state, RngFactory(8), loaded.balance).facilities[-1].yield_rate
    assert a == b and a != c
    assert a == pytest.approx(0.92, abs=0.05)


def test_plant_takes_over_from_the_contract(loaded: LoadedData) -> None:
    """Plants first, then contracts (26.2); its cost per unit run posts at sale."""
    data, balance = loaded.game_data, loaded.balance
    state = _device(fresh_game(loaded))
    pid = _pid(state, "Pebble Phone")
    state = _contract(state, pid, 5_000)
    state = _plant(state, loaded, 5_000, staff=5, skill=14.0)
    state = plant_yields(state, RngFactory(7), balance)
    out = phases.run_markets(state, RngFactory(4), balance, data)
    row = out.state.production_of(pid)
    assert row is not None
    plant = out.state.facilities[-1]
    assert row.plant_units == pytest.approx(5_000 * plant.yield_rate)
    assert row.contract_units == pytest.approx(5_000)
    assert plant.run_units == pytest.approx(5_000)


def test_plant_cost_at_80_and_30_percent(loaded: LoadedData) -> None:
    """26.6 target 3 and 26.7: at 80% use 0.68 of a $13 fee, at 30% 1.40."""
    kind = loaded.balance.facility.kinds["assembly_plant"]
    capex = ff.capex_cents(20_000, kind.capex_per_unit_cents, 1.0)
    from tst.sim.hardware import formulas as hf

    args = (kind.fixed_opex_cents, kind.variable_cents, capex, kind.life_months)
    high = hf.plant_cost_per_good_unit(20_000, 16_000, 0.92, *args)
    low = hf.plant_cost_per_good_unit(20_000, 6_000, 0.92, *args)
    assert high is not None and low is not None
    assert high / 1_300 <= 0.70
    assert low / 1_300 >= 1.30


def test_selling_spare_plant_capacity(loaded: LoadedData) -> None:
    """A contract-manufacturing product sells spare plant capacity, capped by it (26.2)."""
    data, balance = loaded.game_data, loaded.balance
    state = _plant(fresh_game(loaded), loaded, 20_000, staff=20, skill=14.0)
    state = _act(state, SellPlantCapacity(_founder(state)), loaded)
    cm = next(
        p for p in state.products if p.category == "contract_manufacturing" and p.company_id == 1
    )
    assert cm.category == "contract_manufacturing" and cm.status == "live"
    with pytest.raises(FacilityRuleError):
        _act(state, SellPlantCapacity(_founder(state)), loaded)
    from tst.sim.state import with_product_segment

    seg = state.product_segment(cm.id, "device_oems")
    assert seg is not None
    state = with_product_segment(state, replace(seg, customers=5.0))  # 50,000 units wanted
    state = plant_yields(state, RngFactory(7), balance)
    out = phases.run_markets(state, RngFactory(4), balance, data)
    seg = out.state.product_segment(cm.id, "device_oems")
    assert seg is not None
    assert seg.customers * 10_000 <= 20_000 + 1e-6
    assert out.state.facilities[-1].sold_units == pytest.approx(seg.customers * 10_000)
    assert _lines(out.entries, COGS) == round(out.state.facilities[-1].sold_units * 300)


def test_build_plant_in_a_city(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    founder = _founder(state)
    state = _act(
        state, BuildFacility(founder, "assembly_plant", "east_asia", 20_000, None, SHENZHEN), loaded
    )
    plant = state.facilities[-1]
    assert (plant.kind, plant.city, plant.capacity) == ("assembly_plant", SHENZHEN, 20_000)
    assert plant.capex_cents == (20_000 * 30_000)
    with pytest.raises(FacilityRuleError):
        _act(state, BuildFacility(founder, "assembly_plant", "east_asia", 500), loaded)
    with pytest.raises(FacilityRuleError):
        _act(
            state,
            BuildFacility(founder, "assembly_plant", "europe", 20_000, None, SHENZHEN),
            loaded,
        )


def test_plants_are_not_compute(loaded: LoadedData) -> None:
    """A plant serves no compute, has no outages and costs its fixed cost a live month."""
    from tst.sim.facilities import compute

    state = _plant(fresh_game(loaded), loaded, 5_000, staff=5, skill=14.0)
    assert compute.live_facilities(state, 1, loaded.balance) == []
    lines = lifecycle.operating_lines(state, 1, loaded.balance)
    assert lines == [("Assembly plant operations", COGS, 2_000_000, None)]


# --- Sub-task 5: fabless chips ---------------------------------------------------------------


def _chip(state: GameState, chip: str = "chips_mobile_soc", price: int = 4_000) -> GameState:
    return with_product(
        state,
        category=chip,
        prices={"device_oems": price},
        quality=70.0,
        brand=50.0,
        feature_points=10_000.0,
        name="Pebble Silicon",
        root=False,
    )


def test_internal_chips_book_no_revenue(loaded: LoadedData) -> None:
    """A device using its own SoC pays the chip's unit cost; the chip product books no
    revenue for it (ADR-0020 4)."""
    data, balance = loaded.game_data, loaded.balance
    state = _device(fresh_game(loaded))
    dev = _pid(state, "Pebble Phone")
    state = _chip(state, price=10**7)  # the market buys none at this price
    chip = _pid(state, "Pebble Silicon")
    state = _contract(state, dev, 1_000)
    state = _contract(state, chip, 10, kind="wafer")  # 10 x 600 x 0.70 = 4,200 chips
    out = phases.run_markets(state, RngFactory(4), balance, data)
    chip_row, dev_row = out.state.production_of(chip), out.state.production_of(dev)
    assert chip_row is not None and dev_row is not None
    assert dev_row.own_chips == pytest.approx(1_000) and dev_row.bought_chips == pytest.approx(0)
    assert chip_row.internal_units == pytest.approx(1_000) and chip_row.units == 0
    unit = chips.unit_cost_cents(out.state, out.state.product(chip), balance, data)  # type: ignore[arg-type]
    assert unit == pytest.approx(900_000 / (600 * 0.70) + 800)
    assert dev_row.chip_cents == round(1_000 * unit)
    revenue = [e for e in out.entries if e.memo == "Revenue: Pebble Silicon"]
    assert revenue == []


def test_chip_capacity_and_wafer_take_or_pay(loaded: LoadedData) -> None:
    data, balance = loaded.game_data, loaded.balance
    state = _chip(fresh_game(loaded), price=10**7)
    chip = _pid(state, "Pebble Silicon")
    state = _contract(state, chip, 10, kind="wafer")
    product = state.product(chip)
    assert product is not None
    assert chips.chip_capacity(state, product, balance, data) == pytest.approx(10 * 600 * 0.70)
    state, entries = production.settle(state, None, {}, balance, data)  # no wafer used
    assert _lines(tuple(entries), GENERAL_ADMIN) == round(10 * 900_000 * 0.3)


def test_sign_wafer_contract(loaded: LoadedData) -> None:
    state = _chip(fresh_game(loaded), chip="chips_ai_accelerator")
    chip = _pid(state, "Pebble Silicon")
    state = _act(state, SignWaferContract(_founder(state), chip, "samsung", 100, 24), loaded)
    (c,) = state.production_contracts
    # Samsung's 0.95 on the wafer price, x the chip mix at spot (M17, 33.2)
    mix = loaded.balance.commodity.mixes["foundry_wafer"]
    scale = costs.apply_mix(1.0, mix, costs.mix_index(state, mix, loaded.game_data))
    assert c.kind == "wafer" and c.price_cents == pytest.approx(900_000 * 0.95 * scale)


def test_advanced_node_crunch(loaded: LoadedData) -> None:
    """Advanced nodes are short in 2023-2024; mobile SoCs are not."""
    data, balance = loaded.game_data, loaded.balance
    state = replace(fresh_game(loaded), turn=ym_to_turn(2023, 6))
    for chip_cat, share in (("chips_ai_accelerator", 0.60), ("chips_mobile_soc", 1.0)):
        s = _chip(state, chip=chip_cat)
        pid = _pid(s, "Pebble Silicon")
        s = _contract(s, pid, 10, kind="wafer")
        c = s.production_contracts[-1]
        assert chips.wafers_delivered(s, c, balance, data) == pytest.approx(10 * share)


def test_gpu_capex_falls_with_own_accelerators(loaded: LoadedData) -> None:
    """Own GPU data centres with the company's own accelerator: capex x (0.4 + 0.6 x own
    cost / market price) (26.3), at least 20% lower (26.6 target 4)."""
    data, balance = loaded.game_data, loaded.balance
    state = fresh_game(loaded)
    before = lifecycle.quote(state, 1, "data_centre_gpu", "north_america", 500, balance, data)
    state = _chip(state, chip="chips_ai_accelerator", price=150_000)
    chip = _pid(state, "Pebble Silicon")
    state = _contract(state, chip, 10, kind="wafer")
    after = lifecycle.quote(state, 1, "data_centre_gpu", "north_america", 500, balance, data)
    factor = chips.gpu_capex_factor(state, 1, balance, data)
    assert factor < 0.8
    assert after.capex_cents == round(before.capex_cents * factor)
    general = lifecycle.quote(state, 1, "data_centre_general", "north_america", 500, balance, data)
    general_before = lifecycle.quote(
        fresh_game(loaded), 1, "data_centre_general", "north_america", 500, balance, data
    )
    assert general.capex_cents == general_before.capex_cents


def test_chip_yield_from_the_lead(loaded: LoadedData) -> None:
    from tst.sim.research.models import EraArrival, ResearchLead

    state = replace(fresh_game(loaded), research_leads=(ResearchLead(1, "chip_design", 20.0),))
    assert chips.chip_yield(state, 1, loaded.balance, loaded.game_data) == pytest.approx(0.76)
    rich = replace(state, research_leads=(ResearchLead(1, "chip_design", 200.0),))
    assert chips.chip_yield(rich, 1, loaded.balance, loaded.game_data) == pytest.approx(0.92)
    after = replace(rich, era_arrivals=(EraArrival("chiplets", 200),))
    assert chips.chip_yield(after, 1, loaded.balance, loaded.game_data) == pytest.approx(0.95)


def test_a_month_with_hardware_balances(loaded: LoadedData) -> None:
    """A whole turn with a device, a chip, contracts and a plant posts balanced entries."""
    data, balance = loaded.game_data, loaded.balance
    state = _device(fresh_game(loaded))
    dev = _pid(state, "Pebble Phone")
    state = _chip(state)
    chip = _pid(state, "Pebble Silicon")
    state = _contract(_contract(state, dev, 2_000), chip, 5, kind="wafer")
    state = _plant(state, loaded, 5_000, staff=3, skill=12.0)
    result = advance_turn(state, Decisions(), RngFactory(3), balance, data, RICH)
    for e in result.ledger_entries:
        assert sum(line.amount for line in e.lines) == 0
    assert result.new_state.production_of(dev) is not None
    _ = Product  # keep the import for type readers
