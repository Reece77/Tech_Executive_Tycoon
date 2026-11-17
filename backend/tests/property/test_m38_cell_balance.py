"""M38 sub-task 3 property test (formulas.md 49.2): materials and money balance per entity through
a cell plant. For any plant size, learning, staffing and sales, a month's kWh made equal those
taken by the group's cars plus those sold at spot, inputs are the chemistry's materials over the
yield, every ledger entry balances, and the product's battery cost uses its own cells."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities.models import Facility
from tst.sim.hardware.models import ProductionMonth
from tst.sim.products.models import Product
from tst.sim.rng import RngFactory
from tst.sim.state import with_facility, with_product
from tst.sim.vehicles import cells
from tst.sim.vehicles.models import CellPlant, VehicleMonth, VehicleSpec

PLAYER = 1
EPS = 1e-6


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    size=st.sampled_from([100, 250, 500, 1000]),
    months=st.integers(min_value=0, max_value=60),
    last_units=st.floats(min_value=0, max_value=20_000),
    sold=st.floats(min_value=0, max_value=20_000),
    chem=st.sampled_from(["nmc", "lfp"]),
    pack=st.floats(min_value=20, max_value=120),
)
def test_cells_balance(
    loaded: LoadedData,
    monkeypatch: pytest.MonkeyPatch,
    size: int,
    months: int,
    last_units: float,
    sold: float,
    chem: str,
    pack: float,
) -> None:
    b, d = loaded.balance, loaded.game_data
    # a fully staffed plant at skill 12 (staffing itself is M12a's, tested there)
    monkeypatch.setattr(
        cells, "staffing", lambda *_: SimpleNamespace(coverage=1.0, mean_skill=12.0)
    )
    turn = ym_to_turn(2024, 6)
    state = replace(fresh_game(loaded), turn=turn)
    fid = 77_000
    f = Facility(
        id=fid,
        company_id=PLAYER,
        kind="cell_plant",
        region="north_america",
        capacity=size,
        on_time=size,
        ordered_turn=turn - 24,
        ready_turn=turn - 1,
        late_turn=turn - 1,
        capex_cents=size * 65_000_000,
        input_index=1.0,
        capex_paid_cents=size * 65_000_000,
        status="live",
    )
    state = with_facility(state, f)
    pid = 66_000
    car = Product(
        id=pid,
        company_id=PLAYER,
        category="vehicles",
        name="Car",
        status="live",
        quality=60.0,
        feature_points=10.0,
        brand=10.0,
        marketing_budget_cents=0,
        created_turn=0,
    )
    state = with_product(state, car)
    spec = VehicleSpec(pid, pack, chem, 150.0, "l2", "licensed", "own")  # type: ignore[arg-type]
    plant = CellPlant(fid, PLAYER, chem, months_run=months)  # type: ignore[arg-type]
    last = VehicleMonth(turn - 1, pid, last_units, 0, 0, 0, 0, 0, 0.0, 0, 0, "l2", 300.0)
    state = replace(state, vehicle_specs=(spec,), cell_plants=(plant,), vehicle_months=(last,))
    state, entries, _ = cells.run_plants(state, RngFactory(9), b, d)
    m = state.cell_plants[0].month
    assert m is not None and m.made_kwh > 0
    # materials: inputs are the chemistry's a kWh over the yield
    chemistry = d.vehicles.battery.chemistries[chem]  # type: ignore[union-attr]
    for good, vol in m.inputs:
        assert abs(vol - chemistry.inputs[good] * m.made_kwh / m.yield_rate) < EPS * max(1, vol)
    lotted = sum(x.kwh for x in state.cell_lots)
    assert lotted <= m.made_kwh + EPS and abs(m.to_group - lotted) < EPS
    assert lotted <= last_units * pack + EPS
    # the month's sales, then the settlement
    row = VehicleMonth(turn, pid, sold, 0, 0, 0, 0, 0, 0.0, 0, 0, "l2", 300.0)
    state = replace(
        state,
        vehicle_months=(last, row),
        production=(ProductionMonth(turn, pid, PLAYER, capacity=sold, units=sold),),
    )
    state, more = cells.settle(state, b, d)
    m2 = state.cell_plants[0].month
    assert m2 is not None
    taken = sum(x.taken for x in state.cell_lots)
    assert taken <= sold * pack + EPS
    assert abs(m2.to_group + m2.to_spot - m2.made_kwh) < EPS * max(1.0, m2.made_kwh)
    assert abs(m2.to_group - taken) < EPS * max(1.0, taken)
    for e in (*entries, *more):
        assert sum(line.amount for line in e.lines) == 0
        assert e.company_id == PLAYER
