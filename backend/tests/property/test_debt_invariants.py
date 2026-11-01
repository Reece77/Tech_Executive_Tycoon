"""Debt invariants (docs/formulas.md 20.3, M10 sub-task 4): with any loans, repayments and
months, the ledger balances and principal paid never exceeds principal borrowed."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tst.balance.game import PLAYER, start_game
from tst.loader import load_all
from tst.sim.finance import debt
from tst.sim.ledger import DEBT, apply_entries
from tst.sim.state import with_company

LOADED = load_all(Path(__file__).resolve().parents[2] / "data")
BASE = start_game(LOADED, 7, scenario="funded_spinout")
MAX = debt.capacity_cents(BASE.state, PLAYER, "venture_debt", LOADED.balance)


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    amount=st.integers(min_value=LOADED.balance.debt.min_cents, max_value=MAX),
    months=st.integers(min_value=1, max_value=40),
    repay_at=st.integers(min_value=0, max_value=40),
    repay_share=st.floats(min_value=0, max_value=1),
    burn=st.integers(min_value=0, max_value=10**10),
)
def test_ledger_balances_and_principal_bounded(
    amount: int, months: int, repay_at: int, repay_share: float, burn: int
) -> None:
    balance, data = LOADED.balance, LOADED.game_data
    state, loan, entries = debt.sign(BASE.state, PLAYER, "venture_debt", amount, balance, data)
    balances = apply_entries(BASE.balances, entries)
    for month in range(months):
        state = with_company(state, replace(state.company(PLAYER), burn_history=(burn,)))
        if month == repay_at:
            current = state.loan(loan.id)
            assert current is not None
            if current.active:
                state, _, posted = debt.repay(
                    state, current, round(current.balance_cents * repay_share), "early"
                )
                balances = apply_entries(balances, posted)
        state, posted, _ = debt.debt_month(state, balances, balance, data)
        balances = apply_entries(balances, posted)
        for entry in posted:
            assert sum(line.amount for line in entry.lines) == 0
        state = replace(state, turn=state.turn + 1)
        current = state.loan(loan.id)
        assert current is not None
        assert 0 <= current.principal_paid_cents <= current.principal_cents
        assert current.balance_cents == current.principal_cents - current.principal_paid_cents
        assert -balances.get((PLAYER, DEBT), 0) == current.balance_cents
    assert sum(balances.values()) == 0
