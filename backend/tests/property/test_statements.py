"""Statement invariants over random balanced ledgers (formulas.md 14.1): assets = liabilities +
paid-in equity + accumulated result at every month end; cash flow's parts add up to the cash
account's movement over every period; the P&L's net result is the accumulated result's
movement."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tst.sim.data_models import AccountType
from tst.sim.finance import statements as fs

TYPES: dict[str, AccountType] = {
    "1000_cash": "asset",
    "1100_receivables": "asset",
    "2600_safes": "liability",
    "3000_common_equity": "equity",
    "3100_preferred_equity": "equity",
    "4000_revenue_subscriptions": "revenue",
    "6000_salaries": "expense",
    "6300_compute": "expense",
    "6900_general_admin": "expense",
    "7000_interest": "expense",
}
amounts = st.integers(min_value=-(10**11), max_value=10**11)


@st.composite
def ledgers(draw: st.DrawFn) -> list[tuple[int, str, int]]:
    """Random balanced entries spread over up to 30 turns, flattened to lines."""
    lines: list[tuple[int, str, int]] = []
    for _ in range(draw(st.integers(min_value=0, max_value=25))):
        turn = draw(st.integers(min_value=0, max_value=29))
        head = draw(
            st.lists(st.tuples(st.sampled_from(sorted(TYPES)), amounts), min_size=1, max_size=4)
        )
        lines += [(turn, acc, amt) for acc, amt in head]
        lines.append((turn, draw(st.sampled_from(sorted(TYPES))), -sum(a for _, a in head)))
    return lines


@settings(max_examples=150)
@given(ledgers(), st.sampled_from(fs.PERIODS))
def test_statements_reconcile(lines: list[tuple[int, str, int]], period: fs.Period) -> None:
    last = max((t for t, _, _ in lines), default=0)
    for turn in range(last + 1):
        sheet = fs.balance_sheet(lines, TYPES, turn)
        assert sheet.total_assets == sheet.total_liabilities_and_equity
    for first, end in fs.period_bounds(period, last):
        flow = fs.cash_flow(lines, TYPES, first, end)
        cash_moved = sum(a for t, acc, a in lines if first <= t <= end and acc == "1000_cash")
        assert flow.change_in_cash == cash_moved
        assert flow.reconciles
        pnl = fs.profit_and_loss(lines, TYPES, first, end)
        before = fs.balance_sheet(lines, TYPES, first - 1).accumulated_result
        after = fs.balance_sheet(lines, TYPES, end).accumulated_result
        assert pnl.net_result == after - before


@given(st.integers(min_value=0, max_value=200), st.sampled_from(fs.PERIODS))
def test_periods_cover_every_turn_once(last: int, period: fs.Period) -> None:
    bounds = fs.period_bounds(period, last)
    covered = [t for first, end in bounds for t in range(first, end + 1)]
    assert covered == list(range(last + 1))
