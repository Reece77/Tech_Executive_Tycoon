"""docs/formulas.md 22.8 worked examples, the 22.2 tables and the 22.4 history (M12a sub-task 1)."""

from __future__ import annotations

import itertools

import pytest

from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities import formulas as ff
from tst.sim.rng import STREAM_IDS


def test_unit_cost_example(loaded: LoadedData) -> None:
    """500 general CU, full: depreciation 500 x $24,000 / 60 = $200,000, operating
    500 x $250 = $125,000: $325,000 a month, $650 a CU against $1,000 spot; at 40% use
    $325,000 / 200 = $1,625 per used CU."""
    kind = loaded.balance.facility.kinds["data_centre_general"]
    capex = ff.capex_cents(500, kind.capex_per_unit_cents, 1.0)
    assert ff.monthly_depreciation_cents(capex, kind.life_months) == 200_000_00
    assert 500 * kind.opex_per_unit_cents == 125_000_00
    month = ff.monthly_cost_cents(500, capex, kind.life_months, kind.opex_per_unit_cents)
    assert month == 325_000_00
    assert ff.cost_per_used_unit_cents(month, 500) == 650_00
    assert ff.cost_per_used_unit_cents(month, 200) == 1_625_00
    spot = loaded.balance.compute.goods["compute_general"].spot_cents
    assert spot == 1_000_00
    # break-even at 65% use (22.2)
    assert ff.cost_per_used_unit_cents(month, 500 * 0.65) == pytest.approx(spot)


def test_reliability_example(loaded: LoadedData) -> None:
    """2,000 CU needs 10 staff; with 8 at mean infrastructure skill 15, c_f = 0.8 and
    rel = 100 x 0.8 x (0.7 + 0.225) = 74, an outage chance of 0.002 x 2.6 = 0.52% a month."""
    fb = loaded.balance.facility
    kind = fb.kinds["data_centre_general"]
    need = ff.staff_needed(2000, kind.staff_per)
    assert need == 10
    c = ff.coverage(8, need)
    assert c == pytest.approx(0.8)
    rel = ff.reliability(c, 15, fb.reliability_floor, fb.reliability_skill)
    assert rel == pytest.approx(74)
    assert ff.outage_chance(rel, 0.002) == pytest.approx(0.0052)  # 22.8 uses base 0.002
    assert ff.outage_chance(50, 0.002) == pytest.approx(0.01)  # 1% a month at 50 (22.5)
    assert ff.outage_chance(95, 0.002) == pytest.approx(0.001)  # 0.1% at 95


def test_gpu_build_in_the_crunch(loaded: LoadedData) -> None:
    """500 GPU CU in Jul 2023 (GPU index 1.60, allocation 40%): capex 500 x $64,000 = $32M;
    200 CU complete on time and 300 arrive 6 months late. (22.8 states $40,000 a CU; M12a
    tuned balance.yaml to $20,000 for target 4, Reece 2026-11-02.)"""
    assert ff.capex_cents(500, 40_000_00, 1.60) == 32_000_000_00
    on_time, late, months = ff.allocation_split(500, 0.40, loaded.balance.supply.delay_step)
    assert (on_time, late, months) == (200, 300, 6)
    assert ff.allocation_split(500, 1.0, 0.1) == (500, 0, 0)
    assert ff.allocation_split(2000, 0.70, 0.1) == (1400, 600, 3)


def test_kind_table(loaded: LoadedData) -> None:
    """The 22.2 table is data (the GPU column tuned for target 4: $40,000 and $500 in 22.2;
    Reece 2026-11-02)."""
    kinds = loaded.balance.facility.kinds
    general, gpu = kinds["data_centre_general"], kinds["data_centre_gpu"]
    assert (general.capex_per_unit_cents, general.build_months) == (24_000_00, 12)
    assert (general.opex_per_unit_cents, general.life_months) == (250_00, 60)
    assert (gpu.capex_per_unit_cents, gpu.build_months) == (20_000_00, 9)
    assert (gpu.opex_per_unit_cents, gpu.life_months) == (200_00, 48)
    assert (general.input_good, gpu.input_good) == ("server", "gpu")
    assert general.staff_per == gpu.staff_per == 200
    assert loaded.balance.facility.sizes == (100, 500, 2000, 10000)
    assert loaded.balance.facility.build_energy == loaded.balance.facility.close_energy == 12
    assert loaded.balance.supply.contract_energy == 6
    assert loaded.balance.facility.sale_share == 0.5
    # full-use economics: $24,000 / 60 + $250 = $650 a CU (22.2)
    capex = ff.capex_cents(1, general.capex_per_unit_cents, 1.0)
    assert ff.monthly_cost_cents(1, capex, 60, general.opex_per_unit_cents) == 650_00


def test_cumulative_depreciation_ends_at_capex() -> None:
    """Each part depreciates from the month it goes live; the total is exactly the capex."""
    capex = 32_000_000_00
    total = [ff.cumulative_depreciation_cents(capex, 500, 200, 10, 16, 48, t) for t in range(80)]
    assert total[9] == 0 and total[10] > 0
    assert total[-1] == capex
    assert all(b >= a for a, b in itertools.pairwise(total))
    paid = 0
    for month in range(9):
        paid += ff.capex_payment_cents(1000, 9, paid, month)
    assert paid == 1000


def test_cu_need_and_spot(loaded: LoadedData) -> None:
    """A CU is $1,000 of hosting a month at index 1.0 (22.1)."""
    assert ff.cu_need(40_000_00, 1_000_00) == 40
    cg = loaded.balance.compute
    assert cg.goods["compute_gpu"].spot_index == "ai"
    assert cg.goods["compute_general"].spot_index == "flat"
    assert cg.indexed_good == "compute_gpu"


def test_cloud_features(loaded: LoadedData) -> None:
    """50 + 2 x lead, capped at 100 (22.3)."""
    cg = loaded.balance.compute
    assert ff.feature_target(0, cg.feature_base, cg.feature_per_lead) == 50
    assert ff.feature_target(10, cg.feature_base, cg.feature_per_lead) == 70
    assert ff.feature_target(40, cg.feature_base, cg.feature_per_lead) == 100


def _index(loaded: LoadedData, good: str, year: int, month: int) -> float:
    components = loaded.game_data.components
    assert components is not None
    return components.good(good).index_at(ym_to_turn(year, month))


def test_component_history(loaded: LoadedData) -> None:
    """22.4: server -8% a year to 2020, +30% Q2 2021 to Q2 2022, back by 2023; GPU -10% a
    year to 2016, +20% a year in 2017-2018, +60% Q1 2023 to Q2 2024; allocation 70% for
    servers in 2021-2022, 40% for GPUs in 2023-2024, else 100%."""
    components = loaded.game_data.components
    assert components is not None
    assert _index(loaded, "server", 2010, 1) == _index(loaded, "gpu", 2010, 1) == 1.0
    assert _index(loaded, "server", 2011, 1) == pytest.approx(0.92, abs=1e-3)
    assert _index(loaded, "server", 2021, 1) == pytest.approx(0.92**11, rel=1e-3)
    shortage = _index(loaded, "server", 2022, 4) / _index(loaded, "server", 2021, 4)
    assert shortage == pytest.approx(1.30, abs=1e-3)  # 22.7 target 4: 20-40%
    assert _index(loaded, "server", 2023, 1) == pytest.approx(0.92**13, rel=1e-3)
    assert _index(loaded, "gpu", 2017, 1) == pytest.approx(0.9**7, rel=1e-3)
    assert _index(loaded, "gpu", 2019, 1) / _index(loaded, "gpu", 2017, 1) == pytest.approx(
        1.44, abs=1e-3
    )
    crunch = _index(loaded, "gpu", 2024, 6) / _index(loaded, "gpu", 2023, 1)
    assert crunch == pytest.approx(1.60, abs=1e-3)  # 22.7 target 4: 40-80%
    server, gpu = components.good("server"), components.good("gpu")
    assert server.allocation_at(ym_to_turn(2020, 12)) == 1.0
    assert server.allocation_at(ym_to_turn(2021, 1)) == 0.70
    assert server.allocation_at(ym_to_turn(2022, 12)) == 0.70
    assert server.allocation_at(ym_to_turn(2023, 1)) == 1.0
    assert gpu.allocation_at(ym_to_turn(2023, 1)) == gpu.allocation_at(ym_to_turn(2024, 12)) == 0.4
    assert gpu.allocation_at(ym_to_turn(2025, 1)) == 1.0
    assert components.last_turn == ym_to_turn(2025, 12)


def test_supply_balance_matches_the_text(loaded: LoadedData) -> None:
    """22.4's after-2025 rules are data; the streams are ADR-0013's reserved ids."""
    sb = loaded.balance.supply
    assert (sb.change.mean, sb.change.shock_sd) == (-0.08, 0.06)
    assert (sb.shock.monthly, sb.shock.gap_months) == (0.01, 30)
    assert (sb.shock.rise.lo, sb.shock.rise.hi) == (0.25, 0.60)
    assert (sb.shock.allocation.lo, sb.shock.allocation.hi) == (0.40, 0.80)
    assert (sb.shock.months.lo, sb.shock.months.hi) == (6, 18)
    assert (sb.contract_months.lo, sb.contract_months.hi) == (12, 36)
    assert sb.take_or_pay == 0.30
    assert STREAM_IDS["supply"] == 26
    assert STREAM_IDS["facility"] == 27


def test_cloud_hosting_data(loaded: LoadedData) -> None:
    """22.3: the hyperscalers segment and the cloud category; incumbents and entrants."""
    gd = loaded.game_data
    hyper = gd.segment("hyperscalers")
    w = hyper.weights
    assert (w.quality, w.price, w.brand, w.features) == (0.40, 0.40, 0.05, 0.15)
    assert (hyper.base_churn, hyper.adoption, hyper.reach) == (0.005, 0.003, "sales")
    cloud = gd.category("cloud_hosting")
    assert cloud.capacity_market
    assert cloud.segment_keys == ("smb", "mid_market", "enterprise", "hyperscalers")
    for m in cloud.markets:  # p_ref is $1,000 a CU
        assert m.reference_price_cents / m.units_per_customer == 1_000_00
    names = {c.name: c.personality for c in gd.incumbents}
    assert names["Amazon Web Services"] == "aggressive"
    assert names["Microsoft Azure"] == "fast_follower"
    assert names["Rackspace"] == "cost_leader"
    assert names["IBM SoftLayer"] == "premium"
    entrants = {e.name: (e.year, e.month, e.category) for e in gd.entrants}
    assert entrants["Google Cloud"] == (2012, 4, "cloud_hosting")
    assert entrants["CoreWeave"] == (2019, 1, "cloud_hosting")
    codes = gd.account_codes()
    assert {"1500_ppe", "1510_accumulated_depreciation", "6700_depreciation"} <= codes
    assert gd.event_template("facility_outage").is_critical
