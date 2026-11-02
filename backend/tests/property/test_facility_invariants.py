"""Facility invariants (docs/formulas.md 22.2, M12a sub-task 3): with any build, shortage,
life and sale month, the ledger balances, book value never goes below 0, depreciation never
exceeds what was paid, and PPE less accumulated depreciation is the book value."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tst.loader import load_all
from tst.sim.facilities import lifecycle
from tst.sim.facilities.models import Facility
from tst.sim.ledger import ACCUMULATED_DEPRECIATION, PPE, apply_entries
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import with_facility

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


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    kind=st.sampled_from(sorted(LOADED.balance.facility.kinds)),
    capacity=st.sampled_from(LOADED.balance.facility.sizes),
    allocation=st.floats(min_value=0.3, max_value=1.0),
    late_months=st.integers(min_value=0, max_value=8),
    index=st.floats(min_value=0.2, max_value=2.0),
    months=st.integers(min_value=1, max_value=90),
    sell_at=st.integers(min_value=0, max_value=100),
)
def test_ledger_balances_and_book_value_bounded(
    kind: str,
    capacity: int,
    allocation: float,
    late_months: int,
    index: float,
    months: int,
    sell_at: int,
) -> None:
    balance, data = LOADED.balance, LOADED.game_data
    k = balance.facility.kinds[kind]
    on_time = round(capacity * allocation)
    capex = round(capacity * k.capex_per_unit_cents * index)
    facility = Facility(
        id=1,
        company_id=1,
        kind=kind,
        region="north_america",
        capacity=capacity,
        on_time=on_time,
        ordered_turn=0,
        ready_turn=k.build_months,
        late_turn=k.build_months + (late_months if on_time < capacity else 0),
        capex_cents=capex,
        input_index=index,
    )
    state = with_facility(BASE, facility)
    balances: dict[tuple[int, str], int] = {}
    for turn in range(months):
        state = replace(state, turn=turn)
        current = state.facility(1)
        assert current is not None
        if turn == sell_at:
            state, entry, proceeds = lifecycle.sell(state, current, balance, data)
            entries = [entry] if entry else []
            assert 0 <= proceeds <= current.book_value_cents
        else:
            state, entries, _ = lifecycle.facility_month(state, current, balance, data)
        balances = dict(apply_entries(balances, entries))  # each entry sums to 0 (ADR-0003)
        f = state.facility(1)
        assert f is not None
        assert 0 <= f.depreciated_cents <= f.capex_paid_cents <= f.capex_cents
        assert f.book_value_cents >= 0
        if f.status != "closed":
            ppe = balances.get((1, PPE), 0) + balances.get((1, ACCUMULATED_DEPRECIATION), 0)
            assert ppe == f.book_value_cents
        else:
            assert balances.get((1, PPE), 0) == 0
            assert balances.get((1, ACCUMULATED_DEPRECIATION), 0) == 0
            break
    assert sum(balances.values()) == 0
    if state.facility(1) is not None and state.facility(1).status == "live":  # type: ignore[union-attr]
        f = state.facility(1)
        assert f is not None
        if months - 1 >= f.late_turn + k.life_months - 1:
            assert f.depreciated_cents == f.capex_cents  # fully depreciated at the end of life
