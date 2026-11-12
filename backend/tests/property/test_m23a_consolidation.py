"""M23a (Codex review 5 finding 3; formulas.md 31.3, 31.8): non-controlling interest's share of
profit is the outsiders' share of each member's **own** profit, intercompany sales and purchases
included, although consolidation removes those lines from the group's revenue and expenses.

Root R holds sA of A from A's closing; A holds sB of B from B's earlier closing. Random external
trading, and intercompany trades upstream (B or A selling to R or A) and downstream (R or A
selling to A or B). Expected values are computed here from the raw ledgers, independently of the
consolidation code."""

from __future__ import annotations

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from tst.sim.data_models import AccountType
from tst.sim.finance import statements as fs
from tst.sim.finance.consolidation import Line, Member, consolidated_lines
from tst.sim.ledger import (
    CASH,
    COMMON_EQUITY,
    GOODWILL,
    INTERCOMPANY_PURCHASES,
    INTERCOMPANY_SALES,
    INVESTMENT_SUBSIDIARIES,
    NCI,
    NCI_SHARE,
)

REV, COST = "4000_revenue_subscriptions", "6000_salaries"
TYPES: dict[str, AccountType] = {
    CASH: "asset",
    GOODWILL: "asset",
    INVESTMENT_SUBSIDIARIES: "asset",
    COMMON_EQUITY: "equity",
    NCI: "equity",
    REV: "revenue",
    COST: "expense",
    INTERCOMPANY_SALES: "revenue",
    INTERCOMPANY_PURCHASES: "expense",
    NCI_SHARE: "expense",
    "4930_gain_on_disposal": "revenue",
}
LAST = 12
FULL = 10_000
PAIRS = (("B", "A"), ("B", "R"), ("A", "R"), ("R", "A"), ("A", "B"), ("R", "B"))


def _profit(lines: list[Line], turn: int) -> int:
    return -sum(a for t, acc, a in lines if t == turn and TYPES[acc] in ("revenue", "expense"))


def _sum(lines: list[Line], through: int, kinds: tuple[str, ...]) -> int:
    return sum(a for t, acc, a in lines if t <= through and TYPES[acc] in kinds)


def test_codex_reproduction_an_80_percent_supplier_selling_to_its_parent() -> None:
    """The supplier sells services to its parent for 100 cents with 80 cents of external costs:
    its profit is 20, NCI's share 4 (Codex: production emitted -16)."""
    r = [(0, CASH, 10_000), (0, COMMON_EQUITY, -10_000)]
    a = [(0, CASH, 1_000), (0, COMMON_EQUITY, -1_000)]
    r += [(0, INVESTMENT_SUBSIDIARIES, 800), (0, CASH, -800)]  # 80% of its net assets
    a += [(1, CASH, 100), (1, INTERCOMPANY_SALES, -100), (1, COST, 80), (1, CASH, -80)]
    r += [(1, INTERCOMPANY_PURCHASES, 100), (1, CASH, -100)]
    member = Member(a, 0, None, 0, 800, -1_000, stake_bp=8_000, effective=((0, Fraction(4, 5)),))
    lines = consolidated_lines(r, [member], TYPES)
    assert sum(x for t, acc, x in lines if t == 1 and acc == NCI_SHARE) == 4
    assert not any(acc in (INTERCOMPANY_SALES, INTERCOMPANY_PURCHASES) for _, acc, _ in lines)
    assert sum(x for t, _, x in lines if t <= 1) == 0


@st.composite
def groups(draw: st.DrawFn):  # type: ignore[no-untyped-def]
    s_a = draw(st.sampled_from((5_000, 6_000, 8_000, FULL)))
    s_b = draw(st.sampled_from((5_000, 7_500, 9_000, FULL)))
    c_b = draw(st.integers(min_value=0, max_value=3))
    c_a = draw(st.integers(min_value=c_b, max_value=4))
    books: dict[str, list[Line]] = {
        name: [(0, CASH, cash), (0, COMMON_EQUITY, -cash)]
        for name, cash in (("R", 10**9), ("A", 10**7), ("B", 10**6))
    }
    n_b = _sum(books["B"], c_b, ("asset", "liability"))
    paid_b = round(Fraction(s_b, FULL) * n_b)
    books["A"] += [(c_b, INVESTMENT_SUBSIDIARIES, paid_b), (c_b, CASH, -paid_b)]
    equity_b = _sum(books["B"], c_b, ("equity",))
    n_a = _sum(books["A"], c_a, ("asset", "liability"))
    paid_a = round(Fraction(s_a, FULL) * n_a)
    books["R"] += [(c_a, INVESTMENT_SUBSIDIARIES, paid_a), (c_a, CASH, -paid_a)]
    equity_a = _sum(books["A"], c_a, ("equity",))
    ops = draw(
        st.lists(
            st.tuples(
                st.integers(min_value=c_a + 1, max_value=LAST),
                st.sampled_from(("sale", "cost", "intercompany")),
                st.sampled_from(PAIRS),
                st.integers(min_value=1, max_value=10**5),
            ),
            max_size=25,
        )
    )
    for turn, kind, (seller, buyer), amount in sorted(ops):
        if kind == "sale":
            books[seller] += [(turn, CASH, amount), (turn, REV, -amount)]
        elif kind == "cost":
            books[seller] += [(turn, CASH, -amount), (turn, COST, amount)]
        else:
            books[seller] += [(turn, CASH, amount), (turn, INTERCOMPANY_SALES, -amount)]
            books[buyer] += [(turn, INTERCOMPANY_PURCHASES, amount), (turn, CASH, -amount)]
    e_a = Fraction(s_a, FULL)
    e_b = e_a * Fraction(s_b, FULL)
    members = [
        Member(books["A"], c_a, None, c_a, paid_a, equity_a, stake_bp=s_a, effective=((c_a, e_a),)),
        Member(books["B"], c_a, None, c_b, paid_b, equity_b, stake_bp=s_b, effective=((c_a, e_b),)),
    ]
    return books, members, c_a, e_a, e_b


@settings(max_examples=150, deadline=None)
@given(groups())
def test_nci_takes_its_share_of_each_members_own_profit(case) -> None:  # type: ignore[no-untyped-def]
    books, members, c_a, e_a, e_b = case
    lines = consolidated_lines(books["R"], members, TYPES)
    for turn in range(c_a + 1, LAST + 1):
        assert sum(a for t, _, a in lines if t <= turn) == 0, turn
        sheet = fs.balance_sheet(lines, TYPES, turn)
        assert sheet.total_assets == sheet.total_liabilities_and_equity, turn
        expected = round(
            (1 - e_a) * _profit(books["A"], turn) + (1 - e_b) * _profit(books["B"], turn)
        )
        got = sum(a for t, acc, a in lines if t == turn and acc == NCI_SHARE)
        assert got == expected, turn
        # intercompany revenue and expense never reach the group's statements
        assert not any(
            acc in (INTERCOMPANY_SALES, INTERCOMPANY_PURCHASES) for t, acc, _ in lines if t == turn
        )
