"""M12a: compute units, data centres, components, contracts, cloud hosting and outages
(docs/formulas.md 22)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, with_employee, with_product
from tst.loader import LoadedData
from tst.sim.actions import (
    BuildFacility,
    SellCapacity,
    SellFacility,
    SignContract,
    StaffFacility,
    apply_action,
)
from tst.sim.actions.org import CreateUnit
from tst.sim.calendar import ym_to_turn
from tst.sim.decisions import Decisions
from tst.sim.errors import FacilityRuleError, ProductRuleError
from tst.sim.facilities import compute, goods, lifecycle
from tst.sim.facilities.models import Facility
from tst.sim.hiring.phases import monthly_costs
from tst.sim.ledger import (
    ACCUMULATED_DEPRECIATION,
    CASH,
    DEPRECIATION,
    PPE,
    LedgerBalances,
    apply_entries,
)
from tst.sim.people.generator import generate_person
from tst.sim.products.phases import product_costs
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_facility
from tst.sim.turn import advance_turn

RICH: LedgerBalances = {(1, CASH): 10**13}


def _founder(state: GameState) -> int:
    founder = state.founder_of(1)
    assert founder is not None
    return founder.id


def _act(state: GameState, action: object, loaded: LoadedData, balances: LedgerBalances = RICH):
    return apply_action(
        state,
        action,
        RngFactory(1),
        loaded.balance,
        loaded.game_data,
        balances,
        seq=0,  # type: ignore[arg-type]
    )


def _live(
    state: GameState,
    loaded: LoadedData,
    capacity: int = 500,
    kind: str = "data_centre_general",
    region: str = "north_america",
    fid: int | None = None,
    capex_per: int | None = None,
) -> GameState:
    """A live facility built long enough ago to be paid for."""
    k = loaded.balance.facility.kinds[kind]
    per = k.capex_per_unit_cents if capex_per is None else capex_per
    fid = fid if fid is not None else state.next_ids.facility
    facility = Facility(
        id=fid,
        company_id=1,
        kind=kind,
        region=region,
        capacity=capacity,
        on_time=capacity,
        ordered_turn=state.turn - k.build_months,
        ready_turn=state.turn,
        late_turn=state.turn,
        capex_cents=capacity * per,
        input_index=1.0,
        capex_paid_cents=capacity * per,
        status="live",
    )
    state = replace(state, next_ids=replace(state.next_ids, facility=fid + 1))
    return with_facility(state, facility)


def _run(state: GameState, loaded: LoadedData, months: int, balances: LedgerBalances = RICH):
    entries = []
    rng = RngFactory(state.save_meta.master_seed)
    for _ in range(months):
        result = advance_turn(state, Decisions(), rng, loaded.balance, loaded.game_data, balances)
        balances = apply_entries(balances, result.ledger_entries)
        entries += list(result.ledger_entries)
        state = result.new_state
    return state, balances, entries


# --- 22.1 compute units and spot ----------------------------------------------------------------


def test_no_data_centre_costs_exactly_as_before(loaded: LoadedData) -> None:
    """A company that never builds posts exactly the same compute costs (acceptance 2)."""
    state = with_product(
        fresh_game(loaded),
        customers={"smb": 5000.0, "mid_market": 40.0},
        prices={"smb": 5000, "mid_market": 80000},
    )
    assert product_costs(state, 1, loaded.game_data) == product_costs(
        state, 1, loaded.game_data, loaded.balance
    )
    lines = {memo for memo, _, _ in monthly_costs(state, 1, loaded.balance, loaded.game_data)}
    assert "Data centre operations" not in lines


def test_cu_needs_general_and_gpu(loaded: LoadedData) -> None:
    """CU = hosting at index 1.0 / $1,000; AI needs GPU CU (22.1)."""
    state = with_product(fresh_game(loaded), customers={"smb": 5000.0}, prices={"smb": 5000})
    state = with_product(
        state,
        category="ai_models",
        customers={"enterprise": 3.0},
        prices={"enterprise": 2_500_000},
        root=False,
        name="Brain",
    )
    needs = compute.needs(state, 1, loaded.balance, loaded.game_data)
    by_good = {n.good: n.units for n in needs}
    assert by_good["compute_general"] == pytest.approx(5000 * 400 / 100_000)
    assert by_good["compute_gpu"] == pytest.approx(3 * 600_000 / 100_000)
    ai = compute.spot_unit_cents(state, "compute_gpu", loaded.balance, loaded.game_data)
    assert ai == pytest.approx(100_000 * 1.0)  # Jan 2010: the AI index is 1.0


# --- 22.2 data centres ------------------------------------------------------------------------


def test_own_products_served_first_and_spot_falls(loaded: LoadedData) -> None:
    """Own capacity serves own products; their spot hosting falls by the CU served (22.2)."""
    state = with_product(fresh_game(loaded), customers={"smb": 50_000.0}, prices={"smb": 5000})
    before, _ = product_costs(state, 1, loaded.game_data, loaded.balance)  # 200 CU of need
    state = _live(state, loaded, capacity=100)
    alloc = compute.allocate(state, 1, loaded.balance, loaded.game_data)
    assert sum(alloc.own.values()) == pytest.approx(100)
    after, _ = product_costs(state, 1, loaded.game_data, loaded.balance)
    assert after == pytest.approx(before / 2, abs=1)


def test_capacity_serves_its_region_and_neighbour_only(loaded: LoadedData) -> None:
    """A data centre in Europe does not serve the North American home market (19.5)."""
    state = with_product(fresh_game(loaded), customers={"smb": 50_000.0}, prices={"smb": 5000})
    far = _live(state, loaded, capacity=100, region="europe")
    assert compute.allocate(far, 1, loaded.balance, loaded.game_data).own == {}
    near = _live(state, loaded, capacity=100, region="latin_america")  # NA's neighbour
    assert sum(compute.allocate(near, 1, loaded.balance, loaded.game_data).own.values()) > 0


def test_gpu_capacity_serves_only_ai(loaded: LoadedData) -> None:
    state = with_product(fresh_game(loaded), customers={"smb": 50_000.0}, prices={"smb": 5000})
    state = _live(state, loaded, capacity=100, kind="data_centre_gpu")
    assert compute.allocate(state, 1, loaded.balance, loaded.game_data).own == {}


def test_cheapest_capacity_first(loaded: LoadedData) -> None:
    state = with_product(fresh_game(loaded), customers={"smb": 25_000.0}, prices={"smb": 5000})
    state = _live(state, loaded, capacity=100, capex_per=3_000_000)  # dearer, id 1
    state = _live(state, loaded, capacity=100, capex_per=1_000_000)  # cheaper, id 2
    alloc = compute.allocate(state, 1, loaded.balance, loaded.game_data)
    assert alloc.own == {2: pytest.approx(100)}


def test_build_pays_capex_then_depreciates(loaded: LoadedData) -> None:
    """Build action (energy 12): equal capex payments to 1500_ppe during the build, live at
    the ready month, depreciation to 6700/1510 after, operating cost in phase 6 (22.2)."""
    state = fresh_game(loaded)
    founder = _founder(state)
    energy = state.person_state(founder).energy
    out = _act(state, BuildFacility(founder, "data_centre_general", "north_america", 100), loaded)
    state = out.new_state
    assert state.person_state(founder).energy == energy - 12
    (facility,) = state.facilities
    assert facility.capex_cents == 100 * 2_400_000  # index 1.0 in Jan 2010
    assert facility.ready_turn == 12
    state, balances, entries = _run(state, loaded, 14)
    capex = [e for e in entries if e.memo.startswith("Capex")]
    assert len(capex) == 12 and all(e.lines[0].amount == 20_000_000 for e in capex)
    assert balances[(1, PPE)] == 240_000_000
    dep = [e for e in entries if e.memo.startswith("Depreciation")]
    assert [e.turn for e in dep] == [12, 13]
    assert all(e.lines[0].amount == 4_000_000 for e in dep)  # $2.4M / 60
    assert balances[(1, ACCUMULATED_DEPRECIATION)] == -8_000_000
    assert balances[(1, DEPRECIATION)] == 8_000_000
    ops = [line for e in entries if e.memo.startswith("Monthly costs") for line in e.lines]
    assert state.facilities[0].status == "live"
    del ops


def test_build_rules(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    founder = _founder(state)
    with pytest.raises(FacilityRuleError):
        _act(state, BuildFacility(founder, "data_centre_general", "north_america", 300), loaded)
    with pytest.raises(FacilityRuleError):
        _act(state, BuildFacility(founder, "fab", "north_america", 100), loaded)
    with pytest.raises(FacilityRuleError):
        _act(state, BuildFacility(founder, "data_centre_general", "mars", 100), loaded)


def test_sell_for_half_book_value(loaded: LoadedData) -> None:
    state = _live(fresh_game(loaded), loaded, capacity=100)
    facility = state.facilities[0]
    facility = replace(facility, depreciated_cents=40_000_000)
    state = with_facility(state, facility)
    out = _act(state, SellFacility(_founder(state), facility.id), loaded)
    (entry,) = out.ledger_entries
    lines = {line.account: line.amount for line in entry.lines}
    assert lines[CASH] == 100_000_000  # half of 200,000,000 book
    assert lines[PPE] == -240_000_000
    assert lines[ACCUMULATED_DEPRECIATION] == 40_000_000
    assert lines[DEPRECIATION] == 100_000_000
    assert out.new_state.company_facilities(1) == ()


def test_staffing_and_reliability(loaded: LoadedData) -> None:
    """Coverage from DevOps or security engineers in the assigned unit (22.2)."""
    state = fresh_game(loaded)
    founder = _founder(state)
    state = _act(state, CreateUnit(founder, "team", "Ops"), loaded).new_state
    unit = state.units[-1].id
    state = _live(state, loaded, capacity=500)  # needs 3
    fid = state.facilities[0].id
    assert lifecycle.staffing(state, state.facilities[0], loaded.balance).reliability == 0
    rng = RngFactory(9)
    for i in range(2):
        person = generate_person(
            rng.stream(0, "misc", i),
            loaded.game_data,
            loaded.balance,
            0,
            loaded.game_data.role("devops_engineer"),
            "senior",
            "north_america",
            person_id=state.next_ids.person,
        )
        state = replace(state, next_ids=replace(state.next_ids, person=person.id + 1))
        state = with_employee(loaded, state, person, 15_000_000)
        emp = state.employment_of(person.id)
        assert emp is not None
        from tst.sim.state import with_employment

        state = with_employment(state, replace(emp, unit_id=unit))
    state = _act(state, StaffFacility(founder, fid, unit), loaded).new_state
    s = lifecycle.staffing(state, state.facility(fid), loaded.balance)  # type: ignore[arg-type]
    assert (s.staff, s.needed) == (2, 3)
    assert s.coverage == pytest.approx(2 / 3)
    assert s.reliability == pytest.approx(100 * (2 / 3) * (0.7 + 0.3 * s.mean_skill / 20))


# --- 22.4 components, allocation and contracts ------------------------------------------------


def test_history_is_the_same_on_every_seed(loaded: LoadedData) -> None:
    components = loaded.game_data.components
    assert components is not None
    state = fresh_game(loaded)
    for seed in (1, 2, 3):
        for turn in (0, ym_to_turn(2021, 6), ym_to_turn(2023, 9), components.last_turn):
            at = replace(state, turn=turn)
            out = goods.supply_phase(at, RngFactory(seed), loaded.balance, loaded.game_data)
            for g in out.supply:
                assert g.index == components.good(g.good).index_at(turn)
                assert g.allocation == components.good(g.good).allocation_at(turn)


def _path(loaded: LoadedData, seed: int, months: int) -> list:
    components = loaded.game_data.components
    assert components is not None
    state = replace(fresh_game(loaded), turn=components.last_turn + 1)
    rng = RngFactory(seed)
    out = []
    for _ in range(months):
        state = goods.supply_phase(state, rng, loaded.balance, loaded.game_data)
        out.append(state.supply)
        state = replace(state, turn=state.turn + 1)
    return out


def test_after_2025_seeded_and_reproducible(loaded: LoadedData) -> None:
    """Shocks after 2025 come from stream `supply` (22.4): the same seed, the same path."""
    a, b, c = _path(loaded, 5, 120), _path(loaded, 5, 120), _path(loaded, 6, 120)
    assert a == b
    assert a != c
    shocks = [g for months in a for g in months if g.in_shock(g.turn)]
    for g in shocks:
        assert 0.4 <= g.allocation <= 0.8
        assert 0.25 <= g.shock_rise <= 0.60
        assert 6 <= g.shock_months <= 18


def test_shortage_delays_part_of_a_build(loaded: LoadedData) -> None:
    """In the 2021-2022 shortage (server allocation 70%) 30% of a build is 3 months late."""
    state = replace(fresh_game(loaded), turn=ym_to_turn(2021, 6))
    out = _act(
        state, BuildFacility(_founder(state), "data_centre_general", "north_america", 500), loaded
    )
    (f,) = out.new_state.facilities
    assert (f.on_time, f.late_turn - f.ready_turn) == (350, 3)
    assert f.live_capacity(f.ready_turn) == 350
    assert f.live_capacity(f.late_turn) == 500


def test_contract_gives_full_allocation_and_take_or_pay(loaded: LoadedData) -> None:
    state = replace(fresh_game(loaded), turn=ym_to_turn(2021, 6))
    founder = _founder(state)
    out = _act(state, SignContract(founder, "server", 12, 1000), loaded)
    state = out.new_state
    (contract,) = state.contracts
    index = goods.index_now(state, "server", loaded.game_data)
    assert contract.index == pytest.approx(index)
    state = _act(
        state,
        BuildFacility(founder, "data_centre_general", "north_america", 500, contract.id),
        loaded,
    ).new_state
    (f,) = state.facilities
    assert f.on_time == 500 and f.late_turn == f.ready_turn
    assert state.contract(contract.id).used == 500  # type: ignore[union-attr]
    later = replace(state, turn=contract.end_turn + 1)
    settled, entries, _ = lifecycle.settle_contracts(later, loaded.balance)
    (entry,) = entries
    assert entry.lines[0].amount == round(500 * contract.unit_value_cents * 0.3)
    assert settled.contract(contract.id).status == "settled"  # type: ignore[union-attr]
    with pytest.raises(FacilityRuleError):
        _act(state, SignContract(founder, "server", 6, 100), loaded)


# --- 22.3 cloud hosting -----------------------------------------------------------------------


def test_cloud_category_only_from_infrastructure(loaded: LoadedData) -> None:
    from tst.sim.actions import CreateProduct

    state = fresh_game(loaded)
    with pytest.raises(ProductRuleError):
        _act(state, CreateProduct(_founder(state), "X", "cloud_hosting", ("smb",)), loaded)
    with pytest.raises(FacilityRuleError):
        _act(state, SellCapacity(_founder(state)), loaded)


def test_cloud_customers_capped_by_spare(loaded: LoadedData) -> None:
    """Customers' CU never exceed the spare capacity (22.3), and sold CU count as used."""
    state = with_product(fresh_game(loaded), customers={"smb": 25_000.0}, prices={"smb": 5000})
    state = _live(state, loaded, capacity=500)  # own use 100 CU
    state = _act(state, SellCapacity(_founder(state)), loaded).new_state
    cloud = compute.capacity_product(state, 1, loaded.game_data)
    assert cloud is not None and cloud.status == "live"
    from tst.sim.state import with_product_segment

    seg = state.product_segment(cloud.id, "smb")
    assert seg is not None
    state = with_product_segment(state, replace(seg, customers=1000.0))  # 4,000 CU wanted
    from tst.sim.facilities.cloud import trim_to_capacity

    trimmed, removed = trim_to_capacity(state, loaded.balance, loaded.game_data)
    seg = trimmed.product_segment(cloud.id, "smb")
    assert seg is not None and seg.customers * 4 == pytest.approx(400)
    alloc = compute.allocate(trimmed, 1, loaded.balance, loaded.game_data)
    assert alloc.used(state.facilities[0].id) == pytest.approx(500)
    assert removed[(cloud.id, "smb")] == pytest.approx(900)
    hosting, _ = product_costs(trimmed, 1, loaded.game_data, loaded.balance)
    assert hosting == 0  # every CU, own and sold, comes from the data centre


def test_cloud_quality_is_reliability_and_features_from_lead(loaded: LoadedData) -> None:
    from tst.sim.facilities.cloud import refresh_product
    from tst.sim.products.formulas import feature_score

    state = _live(fresh_game(loaded), loaded, capacity=100)
    state = _act(state, SellCapacity(_founder(state)), loaded).new_state
    state = refresh_product(state, 1, loaded.balance, loaded.game_data)
    cloud = compute.capacity_product(state, 1, loaded.game_data)
    assert cloud is not None
    assert cloud.quality == 0  # nobody staffs it
    category = loaded.game_data.category("cloud_hosting")
    assert feature_score(cloud.feature_points, category, state.turn) == pytest.approx(50)


# --- 22.5 outages -----------------------------------------------------------------------------


def test_unstaffed_data_centre_has_outages_as_critical_events(loaded: LoadedData) -> None:
    """At reliability 0 the chance is base x 10 a month; an outage costs hosted products
    customers and queues a critical event (22.5)."""
    ob = loaded.balance.facility.outage
    assert ob.base * 10 > 0
    state = with_product(fresh_game(loaded), customers={"smb": 25_000.0}, prices={"smb": 5000})
    state = _live(state, loaded, capacity=100)
    hit_turn = None
    rng = RngFactory(state.save_meta.master_seed)
    from tst.sim.facilities.outages import roll

    for turn in range(0, 600):
        if roll(replace(state, turn=turn), rng, loaded.balance):
            hit_turn = turn
            break
    assert hit_turn is not None
    from tst.sim.facilities.outages import outages_month

    at = replace(state, turn=hit_turn)
    before = at.product_segment(at.company_products(1)[-1].id, "smb")
    after, logs = outages_month(at, rng, loaded.balance, loaded.game_data)
    seg = after.product_segment(at.company_products(1)[-1].id, "smb")
    assert before is not None and seg is not None
    share = ob.customers_share * loaded.balance.events.caps["customers_pct"][2] / 100
    assert seg.customers == pytest.approx(before.customers * (1 - share))
    (queued,) = after.queued
    assert queued.template_id == "facility_outage" and queued.due_turn == hit_turn + 1
    assert len(after.outages) == 1 and logs
    template = loaded.game_data.event_template("facility_outage")
    assert template.is_critical


def test_cloud_features_follow_the_infrastructure_lead(loaded: LoadedData) -> None:
    """Features = 50 + 2 x the infrastructure lead from M11 (22.3)."""
    from tst.sim.facilities.cloud import refresh_product
    from tst.sim.products.formulas import feature_score
    from tst.sim.research.models import ResearchLead
    from tst.sim.state import with_research_lead

    state = _live(fresh_game(loaded), loaded, capacity=100)
    state = _act(state, SellCapacity(_founder(state)), loaded).new_state
    state = with_research_lead(state, ResearchLead(1, "infrastructure", 10.0))
    state = refresh_product(state, 1, loaded.balance, loaded.game_data)
    cloud = compute.capacity_product(state, 1, loaded.game_data)
    assert cloud is not None
    category = loaded.game_data.category("cloud_hosting")
    assert feature_score(cloud.feature_points, category, state.turn) == pytest.approx(70)
