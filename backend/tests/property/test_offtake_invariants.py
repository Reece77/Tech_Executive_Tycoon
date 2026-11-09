"""Offtake invariants (docs/formulas.md 33.3, M17 sub-task 4): with any volume, prepayment,
signing month, use and supplier, every entry of signing and of each month's settlement
balances, the prepayment account (1200) never goes below zero, it holds exactly what the
deals have left undrawn, and it is empty once every deal has ended or breached."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.helpers import with_product
from tst.loader import load_all
from tst.sim.actions import apply_action
from tst.sim.actions.commodities import SignCommodityContract, SignOfftake
from tst.sim.calendar import ym_to_turn
from tst.sim.commodities import commodity, offtake
from tst.sim.hardware.models import ProductionMonth
from tst.sim.ledger import CASH, PREPAID, apply_entries
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game

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
SUPPLIERS = {"lithium_carbonate": "sqm", "cobalt": "glencore", "neon": "ingas", "copper": "bhp"}
RICH = 10**12


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    good=st.sampled_from(sorted(SUPPLIERS)),
    start=st.integers(min_value=ym_to_turn(2019, 1), max_value=ym_to_turn(2024, 6)),
    years=st.integers(min_value=3, max_value=4),
    volume=st.floats(min_value=0.5, max_value=500.0),
    prepay=st.sampled_from([0.0, 0.1, 0.3]),
    units=st.lists(st.floats(min_value=0.0, max_value=40_000.0), min_size=6, max_size=6),
    contract=st.booleans(),
    seed=st.integers(min_value=1, max_value=1_000),
)
def test_offtake_ledger_balances(
    good: str,
    start: int,
    years: int,
    volume: float,
    prepay: float,
    units: list[float],
    contract: bool,
    seed: int,
) -> None:
    b, d = LOADED.balance, LOADED.game_data
    state = with_product(replace(BASE, turn=start), category="devices", name="Phone")
    phone = next(p.id for p in state.products if p.name == "Phone")
    founder = state.founder_of(1)
    assert founder is not None
    balances = {(1, CASH): RICH}
    rng = RngFactory(seed)
    actions = [SignOfftake(founder.id, good, SUPPLIERS[good], years, volume, prepay)]
    if contract:
        actions.append(SignCommodityContract(founder.id, good, 12, volume))
    signed = 0
    for i, action in enumerate(actions):
        try:
            out = apply_action(state, action, rng, b, d, balances, seq=i + 1)
        except Exception as exc:  # a supplier outside its window refuses: nothing posts
            assert "does not sell" in str(exc)
            continue
        for e in out.ledger_entries:
            assert sum(line.amount for line in e.lines) == 0  # ADR-0003
        balances = apply_entries(balances, out.ledger_entries)
        state = out.new_state
        signed += 1
    end = max((x.end_turn for x in state.commodity_deals), default=start) + 2
    for month, turn in enumerate(range(start + 1, end + 1)):
        state = replace(state, turn=turn)
        state = replace(state, supply=commodity.months(state, rng, b, d))
        state, entries, _ = offtake.start_of_month(state, rng, b, d)
        made = units[month % len(units)]
        row = ProductionMonth(turn, phone, 1, capacity=made, units=made)
        state = replace(state, production=(row,))
        state, more = offtake.settle_month(state, b, d)
        for e in (*entries, *more):
            assert sum(line.amount for line in e.lines) == 0  # ADR-0003
        balances = apply_entries(balances, [*entries, *more])
        held = balances.get((1, PREPAID), 0)
        assert held >= 0
        assert held == sum(x.prepaid_left_cents for x in state.commodity_deals)
    assert all(x.status != "active" for x in state.commodity_deals)
    assert balances.get((1, PREPAID), 0) == 0
    assert len(state.commodity_deals) == signed
