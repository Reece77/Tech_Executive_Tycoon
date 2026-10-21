"""Ledger invariants: entries balance, and posting never creates or destroys money."""

from __future__ import annotations

from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tst.sim.errors import UnbalancedEntryError
from tst.sim.ledger import LedgerEntry, LedgerLine, apply_entries
from tst.sim.money import pct_of

ACCOUNTS = ("1000_cash", "3000_common_equity", "6000_salaries", "6900_general_admin")
amounts = st.integers(min_value=-(10**12), max_value=10**12)


@st.composite
def balanced_lines(draw: st.DrawFn) -> tuple[LedgerLine, ...]:
    head = draw(st.lists(st.tuples(st.sampled_from(ACCOUNTS), amounts), min_size=1, max_size=6))
    lines = [LedgerLine(acc, amt) for acc, amt in head]
    lines.append(LedgerLine(draw(st.sampled_from(ACCOUNTS)), -sum(a for _, a in head)))
    return tuple(lines)


@given(balanced_lines())
def test_balanced_lines_construct(lines: tuple[LedgerLine, ...]) -> None:
    entry = LedgerEntry(turn=0, company_id=1, memo="t", lines=lines)
    assert sum(line.amount for line in entry.lines) == 0


@given(balanced_lines(), amounts.filter(lambda a: a != 0))
def test_unbalanced_lines_raise(lines: tuple[LedgerLine, ...], skew: int) -> None:
    first = lines[0]
    skewed = (LedgerLine(first.account, first.amount + skew), *lines[1:])
    with pytest.raises(UnbalancedEntryError):
        LedgerEntry(turn=0, company_id=1, memo="t", lines=skewed)


@given(amounts)
def test_transfer_balances(amount: int) -> None:
    entry = LedgerEntry.transfer(
        turn=0, company_id=1, memo="t", debit=ACCOUNTS[3], credit=ACCOUNTS[0], amount=amount
    )
    assert sum(line.amount for line in entry.lines) == 0


@given(st.lists(balanced_lines(), max_size=10), st.integers(min_value=1, max_value=3))
def test_posting_preserves_zero_sum(lines_list: list[tuple[LedgerLine, ...]], cid: int) -> None:
    entries = [LedgerEntry(turn=0, company_id=cid, memo="t", lines=ls) for ls in lines_list]
    balances = apply_entries({}, entries)
    assert sum(balances.values()) == 0


def test_single_line_entry_rejected() -> None:
    with pytest.raises(UnbalancedEntryError):
        LedgerEntry(turn=0, company_id=1, memo="t", lines=(LedgerLine("1000_cash", 0),))


def test_float_amount_rejected() -> None:
    lines = (LedgerLine("1000_cash", 1.5), LedgerLine("6900_general_admin", -1.5))  # type: ignore[arg-type]
    with pytest.raises(UnbalancedEntryError):
        LedgerEntry(turn=0, company_id=1, memo="t", lines=lines)


def test_apply_entries_does_not_mutate_input() -> None:
    start = {(1, "1000_cash"): 100}
    entry = LedgerEntry.transfer(
        turn=0, company_id=1, memo="t", debit=ACCOUNTS[3], credit=ACCOUNTS[0], amount=40
    )
    after = apply_entries(start, [entry])
    assert start == {(1, "1000_cash"): 100}
    assert after == {(1, "1000_cash"): 60, (1, "6900_general_admin"): 40}


@given(amounts, st.integers(min_value=0, max_value=100_000))
def test_pct_of_is_nearest_integer(amount: int, bp: int) -> None:
    exact = Fraction(amount * bp, 10_000)
    result = pct_of(amount, bp)
    assert abs(Fraction(result) - exact) <= Fraction(1, 2)
    if abs(Fraction(result) - exact) == Fraction(1, 2):
        assert result % 2 == 0
