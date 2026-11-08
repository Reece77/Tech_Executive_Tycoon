"""M16 sub-task 4 (formulas.md 31.3): consolidation invariants at three levels of ownership
with outside holders. Root R holds a share sA of A from A's closing; A holds a share sB of B
from B's earlier closing, so B enters R's group with A. Random trading, and dividends paid to
every holder pro rata. At every turn: the group's lines total zero and the balance sheet
balances; consolidated cash is the cash of the companies inside; NCI is the outsiders' share
of each company's own net assets (computed here from the raw ledgers)."""

from __future__ import annotations

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from tst.sim.data_models import AccountType
from tst.sim.finance import statements as fs
from tst.sim.finance.consolidation import Line, Member, consolidated_lines
from tst.sim.ledger import CASH, COMMON_EQUITY, GOODWILL, INVESTMENT_SUBSIDIARIES, NCI

REV, COST = "4000_revenue_subscriptions", "6000_salaries"
TYPES: dict[str, AccountType] = {
    CASH: "asset",
    "1100_receivables": "asset",
    GOODWILL: "asset",
    INVESTMENT_SUBSIDIARIES: "asset",
    "2000_payables": "liability",
    COMMON_EQUITY: "equity",
    NCI: "equity",
    REV: "revenue",
    COST: "expense",
    "4990_nci_share_of_profit": "expense",
    "4930_gain_on_disposal": "revenue",
}
LAST = 14
FULL = 10_000


def _sum(lines: list[Line], through: int, kinds: tuple[str, ...], skip: str = "") -> int:
    return sum(a for t, acc, a in lines if t <= through and TYPES[acc] in kinds and acc != skip)


@st.composite
def groups(draw: st.DrawFn):  # type: ignore[no-untyped-def]
    s_a = draw(st.integers(min_value=5_000, max_value=FULL))
    s_b = draw(st.integers(min_value=5_000, max_value=FULL))
    c_b = draw(st.integers(min_value=1, max_value=5))
    c_a = draw(st.integers(min_value=c_b, max_value=8))
    books: dict[str, list[Line]] = {
        name: [(0, CASH, cash), (0, COMMON_EQUITY, -cash)]
        for name, cash in (("R", 10**9), ("A", 10**7), ("B", 10**6))
    }
    ops = draw(
        st.lists(
            st.tuples(
                st.sampled_from(("A", "B", "R")),
                st.integers(min_value=0, max_value=LAST),
                st.sampled_from(("sale", "cost", "dividend", "payable")),
                st.integers(min_value=1, max_value=10**5),
            ),
            max_size=25,
        )
    )
    # B's closing by A: A pays sB x B's net assets for its share (no goodwill)
    n_b = _sum(books["B"], c_b, ("asset", "liability"))
    paid_b = round(Fraction(s_b, FULL) * n_b)
    books["A"] += [(c_b, INVESTMENT_SUBSIDIARIES, paid_b), (c_b, CASH, -paid_b)]
    equity_b = _sum(books["B"], c_b, ("equity",))
    for who, turn, kind, amount in sorted(ops, key=lambda x: (x[1], x[0], x[2], x[3])):
        if kind == "sale":
            books[who] += [(turn, CASH, amount), (turn, REV, -amount)]
        elif kind == "cost":
            books[who] += [(turn, CASH, -amount), (turn, COST, amount)]
        elif kind == "payable":
            books[who] += [(turn, COST, amount), (turn, "2000_payables", -amount)]
        elif kind == "dividend" and ((who == "A" and turn > c_a) or (who == "B" and turn > c_b)):
            parent, share = ("R", s_a) if who == "A" else ("A", s_b)
            to_parent = round(Fraction(share, FULL) * amount)
            books[who] += [(turn, COMMON_EQUITY, amount), (turn, CASH, -amount)]
            books[parent] += [(turn, CASH, to_parent), (turn, INVESTMENT_SUBSIDIARIES, -to_parent)]
    # A's closing by R at c_a (its book then, R's share)
    n_a = _sum(books["A"], c_a, ("asset", "liability"))
    paid_a = round(Fraction(s_a, FULL) * n_a)
    books["R"] += [(c_a, INVESTMENT_SUBSIDIARIES, paid_a), (c_a, CASH, -paid_a)]
    equity_a = _sum(books["A"], c_a, ("equity",))
    e_a = Fraction(s_a, FULL)
    e_b = e_a * Fraction(s_b, FULL)
    members = [
        Member(books["A"], c_a, None, c_a, paid_a, equity_a, stake_bp=s_a, effective=((c_a, e_a),)),
        Member(books["B"], c_a, None, c_b, paid_b, equity_b, stake_bp=s_b, effective=((c_a, e_b),)),
    ]
    return books, members, c_a, e_a, e_b


@settings(max_examples=150, deadline=None)
@given(groups())
def test_three_levels_balance_cash_and_nci(case) -> None:  # type: ignore[no-untyped-def]
    books, members, c_a, e_a, e_b = case
    lines = consolidated_lines(books["R"], members, TYPES)
    for turn in range(LAST + 1):
        assert sum(a for t, _, a in lines if t <= turn) == 0, turn
        sheet = fs.balance_sheet(lines, TYPES, turn)
        assert sheet.total_assets == sheet.total_liabilities_and_equity, turn
        inside = ("R", "A", "B") if turn >= c_a else ("R",)
        cash = sum(a for c in inside for t, acc, a in books[c] if acc == CASH and t <= turn)
        assert sheet.assets.get(CASH, 0) == cash, turn
        if turn < c_a:
            assert sheet.paid_in_equity.get(NCI, 0) == 0
            continue
        own_a = _sum(books["A"], turn, ("asset", "liability"), INVESTMENT_SUBSIDIARIES)
        own_b = _sum(books["B"], turn, ("asset", "liability"))
        expected = round((1 - e_a) * own_a + (1 - e_b) * own_b)
        assert sheet.paid_in_equity.get(NCI, 0) == expected, turn


@settings(max_examples=60, deadline=None)
@given(groups())
def test_wholly_owned_groups_post_no_nci(case) -> None:  # type: ignore[no-untyped-def]
    books, members, *_ = case
    whole = [
        Member(m.lines, m.start, m.end, m.owned_from, m.book_cents, m.equity_cents) for m in members
    ]
    lines = consolidated_lines(books["R"], whole, TYPES)
    assert not any(acc == NCI for _, acc, _ in lines)
