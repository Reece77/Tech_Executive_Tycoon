"""docs/formulas.md 26.7 worked examples, the 26.4 era example and the M12b data (sub-task 1)."""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.chips import formulas as cf
from tst.sim.facilities import formulas as ff
from tst.sim.hardware import formulas as hf
from tst.sim.research import levels
from tst.sim.rng import STREAM_IDS


def test_device_unit_cost_example(loaded: LoadedData) -> None:
    """BOM $180 at index 1.0, a bought SoC at $40 and a contract fee of $13: $233 a unit."""
    hw, ch = loaded.balance.hardware, loaded.balance.chips
    bom = hw.bom["devices"]
    soc = loaded.game_data.category("chips_mobile_soc").market(ch.price_segment)
    assert bom.base_cents == 180_00 and soc.reference_price_cents == 40_00
    assert bom.contract_fee_cents == 13_00
    unit = hf.device_unit_cents(
        hf.bom_cents(bom.base_cents, 1.0), soc.reference_price_cents, bom.contract_fee_cents
    )
    assert unit == 233_00


def test_plant_cost_example(loaded: LoadedData) -> None:
    """A 20,000 units-a-month plant at 80% use, yield 0.92: $4.62 + $4.25 = $8.87 a good
    unit, 0.68 of a $13 fee; at 30% use $18.21, 1.40 of the fee."""
    kind = loaded.balance.facility.kinds["assembly_plant"]
    assert (kind.fixed_opex_cents, kind.variable_cents, kind.life_months) == (20_000_00, 3_00, 96)
    capex = ff.capex_cents(20_000, kind.capex_per_unit_cents, 1.0)
    assert ff.monthly_depreciation_cents(capex, kind.life_months) == 62_500_00
    args = (kind.fixed_opex_cents, kind.variable_cents, capex, kind.life_months)
    high = hf.plant_cost_per_good_unit(20_000, 16_000, 0.92, *args)
    low = hf.plant_cost_per_good_unit(20_000, 6_000, 0.92, *args)
    assert high is not None and low is not None
    assert high == pytest.approx(887, abs=0.5)
    assert pytest.approx(462, abs=0.5) == (20_000_00 + 16_000 * 3_00) / (16_000 * 0.92)
    assert round(high / 13_00, 2) == 0.68
    assert low == pytest.approx(1821, abs=0.5)
    assert round(low / 13_00, 2) == 1.40
    assert hf.plant_cost_per_good_unit(20_000, 0, 0.92, *args) is None


def test_plant_yield_formula(loaded: LoadedData) -> None:
    """yield = 0.85 + 0.10 x mean manufacturing skill / 20: 0.92 at skill 14."""
    y = loaded.balance.hardware.plant_yield
    assert hf.plant_yield(y.base, y.skill_share, 14) == pytest.approx(0.92)
    assert hf.plant_yield(y.base, y.skill_share, 20) == pytest.approx(0.95)


def test_chip_cost_example(loaded: LoadedData) -> None:
    """An AI accelerator at a wafer price of $9,000, 60 chips a wafer and a chip-design lead
    of 20 (yield 0.76): $9,000 / 45.6 + $8 = $205.37."""
    ch = loaded.balance.chips
    t = ch.types["ai_accelerator"]
    assert (t.per_wafer, t.wafer_cents) == (60, 9_000_00)
    y = cf.chip_yield(ch.chip_yield.base, ch.chip_yield.per_lead, 20, ch.chip_yield.cap)
    assert y == pytest.approx(0.76)
    cost = cf.chip_unit_cents(t.wafer_cents, t.per_wafer, y, ch.packaging_cents)
    assert round(cost) == 20_537
    # the cap: 0.92, 0.95 after Chiplets (26.4)
    assert cf.chip_yield(0.70, 0.003, 100, 0.92) == 0.92
    assert cf.chip_yield(0.70, 0.003, 100, 0.95) == 0.95


def test_chips_per_wafer(loaded: LoadedData) -> None:
    types = loaded.balance.chips.types
    assert {k: t.per_wafer for k, t in types.items()} == {
        "mobile_soc": 600,
        "server_cpu": 150,
        "ai_accelerator": 60,
    }


def test_gpu_capex_factor() -> None:
    """capex x (0.4 + 0.6 x own unit cost / market price), never above 1 (26.3)."""
    assert cf.gpu_capex_factor(205.37, 1500, 0.4, 0.6) == pytest.approx(0.4821, abs=1e-4)
    assert cf.gpu_capex_factor(3000, 1500, 0.4, 0.6) == 1.0


def test_take_or_pay() -> None:
    """50% of the fee on unused volume each month (26.2)."""
    assert hf.take_or_pay_cents(1_000, 13_00, 0.5) == 6_500_00
    assert hf.take_or_pay_cents(-5, 13_00, 0.5) == 0


def test_chiplets_example(loaded: LoadedData) -> None:
    """Window 36 months, u = 0.40: t_sched = Jan 2026 + 14 = March 2027; the midpoint is
    July 2027, so the threshold is 30 + 26.375 + 10 + 15 = 81.375."""
    era = next(e for e in loaded.game_data.eras.eras if e.key == "chiplets")
    start, n = levels.window_span(era)
    assert (start, n) == (ym_to_turn(2026, 1), 36)
    assert levels.scheduled_month(start, n, 0.40) == ym_to_turn(2027, 3)
    assert levels.historical_turn(era) == ym_to_turn(2027, 7)
    assert levels.threshold(loaded.game_data, loaded.balance, era) == pytest.approx(81.375)


def test_historical_hardware_eras(loaded: LoadedData) -> None:
    eras = {e.key: e for e in loaded.game_data.eras.eras}
    assert eras["smartphone_ubiquity"].arrival == (2012, 1)
    assert eras["ai_accelerators"].arrival == (2016, 5)
    assert eras["custom_silicon"].arrival == (2020, 11)
    assert eras["edge_ai"].window == ((2027, 1), (2030, 12))
    assert eras["chiplets"].yield_cap == 0.95


def test_stream_ids() -> None:
    """ADR-0013: manufacturing 30, era_window 31 (32 reserved for lane A)."""
    assert STREAM_IDS["manufacturing"] == 30
    assert STREAM_IDS["era_window"] == 31
    assert 32 not in STREAM_IDS.values()


def test_goods_history(loaded: LoadedData) -> None:
    """The 2021 shortage in device and server BOMs; wafers tight in 2021-2022 and advanced
    nodes tight in 2023-2024 (26.2, 26.3)."""
    comp = loaded.game_data.components
    assert comp is not None
    keys = [g.key for g in comp.goods]
    assert keys[:2] == ["server", "gpu"]  # appended: M12a's stream keys do not move
    assert keys[2:] == ["device_bom", "server_bom", "equipment", "foundry_wafer"]
    dev = comp.good("device_bom")
    rise = dev.index_at(ym_to_turn(2022, 4)) / dev.index_at(ym_to_turn(2021, 1))
    assert rise == pytest.approx(1.25, abs=0.01)
    assert dev.allocation_at(ym_to_turn(2021, 6)) == 0.70
    wafer = comp.good("foundry_wafer")
    crunch = ym_to_turn(2023, 6)
    assert wafer.allocation_at(crunch) == 1.0
    assert wafer.allocation_at(crunch, advanced=True) == 0.60
    assert wafer.shortage_start(ym_to_turn(2022, 3)) == ym_to_turn(2021, 1)
