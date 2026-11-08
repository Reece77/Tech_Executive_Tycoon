"""Hardware invariants (docs/formulas.md 26.1-26.3, M12b sub-task 3): with any contract
volume, price, chip source, wafer starts and month, phase 5's entries each balance, the
player's units never exceed what it could make, internal chips never exceed the chip's
supply, and a chip used inside the company books no revenue."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.helpers import with_product
from tst.loader import load_all
from tst.sim.hardware.models import ProductionContract
from tst.sim.ledger import COGS, REVENUE_SUBSCRIPTIONS
from tst.sim.products.phases import run_markets
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import with_production_contract

LOADED = load_all(Path(__file__).resolve().parents[2] / "data")
SCENARIO = LOADED.game_data.scenario("ex_big_tech_founders")
assert SCENARIO is not None
BASE, _ = new_game(
    save_name="p",
    master_seed=1,
    scenario=SCENARIO,
    difficulty="standard",
    company_name="Co",
    founder=DEFAULT_FOUNDER,
    balance=LOADED.balance,
    data=LOADED.game_data,
)


def _contract(state, cid, pid, kind, units, signed):  # type: ignore[no-untyped-def]
    return with_production_contract(
        state,
        ProductionContract(
            id=cid,
            company_id=1,
            product_id=pid,
            kind=kind,
            supplier="foxconn" if kind == "assembly" else "tsmc",
            units=units,
            price_millicents=1_300_000 if kind == "assembly" else 600_000_000,
            signed_turn=signed,
            end_turn=signed + 24,
        ),
    )


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    units=st.integers(min_value=1, max_value=200_000),
    price=st.integers(min_value=5_000, max_value=200_000),
    wafers=st.integers(min_value=0, max_value=200),
    chip_price=st.integers(min_value=1_000, max_value=50_000),
    turn=st.integers(min_value=0, max_value=200),
    signed_before=st.booleans(),
    seed=st.integers(min_value=1, max_value=1_000),
)
def test_phase_5_balances_and_respects_supply(
    units: int,
    price: int,
    wafers: int,
    chip_price: int,
    turn: int,
    signed_before: bool,
    seed: int,
) -> None:
    balance, data = LOADED.balance, LOADED.game_data
    state = replace(BASE, turn=turn)
    state = with_product(
        state,
        category="devices",
        prices={"consumer": price},
        quality=70.0,
        brand=60.0,
        feature_points=10_000.0,
        name="Phone",
    )
    state = with_product(
        state,
        category="chips_mobile_soc",
        prices={"device_oems": chip_price},
        quality=70.0,
        brand=40.0,
        feature_points=10_000.0,
        name="Soc",
        root=False,
    )
    phone = next(p.id for p in state.products if p.name == "Phone")
    soc = next(p.id for p in state.products if p.name == "Soc")
    signed = 0 if signed_before else turn
    state = _contract(state, 1, phone, "assembly", units, signed)
    if wafers:
        state = _contract(state, 2, soc, "wafer", wafers, signed)
    out = run_markets(state, RngFactory(seed), balance, data)
    for e in out.entries:
        assert sum(line.amount for line in e.lines) == 0  # ADR-0003
    row = out.state.production_of(phone)
    assert row is not None
    assert row.units <= units + 1e-6 and row.units <= row.capacity + 1e-6
    assert (
        row.own_chips + row.bought_chips == row.units
        or abs(row.own_chips + row.bought_chips - row.units) < 1e-6
    )
    chip = out.state.production_of(soc)
    assert chip is not None
    assert chip.internal_units + chip.units <= chip.capacity + 1e-6
    assert abs(chip.internal_units - row.own_chips) < 1e-6
    revenue = -sum(
        line.amount
        for e in out.entries
        if e.company_id == 1 and e.memo == "Revenue: Soc"
        for line in e.lines
        if line.account == REVENUE_SUBSCRIPTIONS
    )
    sold_to_market = round(chip.units * chip_price)
    assert abs(revenue - sold_to_market) <= 1  # internal chips earn nothing
    cogs = sum(
        line.amount
        for e in out.entries
        if e.company_id == 1
        for line in e.lines
        if line.account == COGS
    )
    assert cogs == row.cogs_cents + chip.cogs_cents
