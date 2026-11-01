"""Division statements (formulas.md 18.1, M8): divisions plus corporate always sum to the
company's statement, and the shared-services allocation sums to the corporate operating
costs it spreads. Allocations move no cash. M10r finding 2: the lines include loan interest
(below operating profit, 20.3), office rent and division-tagged payroll and product costs, and
the division report's company operating profit equals the real company P&L's."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tst.sim.finance.divisions import division_report, is_operating_cost
from tst.sim.finance.statements import profit_and_loss
from tst.sim.ledger import (
    BENEFITS,
    CASH,
    COMPUTE,
    GENERAL_ADMIN,
    INTEREST,
    MARKETING,
    OTHER_INCOME,
    RECRUITING,
    RENT,
    RESEARCH,
    REVENUE_SUBSCRIPTIONS,
    SALARIES,
)
from tst.sim.org.formulas import allocate_shared
from tst.sim.snapshot import DivisionMonth

TYPES = {
    CASH: "asset",
    REVENUE_SUBSCRIPTIONS: "revenue",
    OTHER_INCOME: "revenue",
    SALARIES: "expense",
    BENEFITS: "expense",
    RENT: "expense",
    GENERAL_ADMIN: "expense",
    RECRUITING: "expense",
    COMPUTE: "expense",
    MARKETING: "expense",
    RESEARCH: "expense",
    INTEREST: "expense",  # below operating profit (20.3)
}
EXPENSES = [a for a, t in TYPES.items() if t == "expense"]
DIVISIONS = [None, 11, 12, 13]

line = st.tuples(
    st.integers(0, 5),
    st.sampled_from([*EXPENSES, REVENUE_SUBSCRIPTIONS, OTHER_INCOME]),
    st.integers(1, 10_000_000),
    st.sampled_from(DIVISIONS),
)


@st.composite
def months(draw: st.DrawFn) -> list[DivisionMonth]:
    out = []
    for turn in range(6):
        out.append(DivisionMonth(turn, 1, None, "Corporate", draw(st.integers(1, 50)), False))
        for d in DIVISIONS[1:]:
            if draw(st.booleans()):
                out.append(
                    DivisionMonth(
                        turn, 1, d, f"D{d}", draw(st.integers(0, 300)), draw(st.booleans())
                    )
                )
    return out


def _signed(
    lines: list[tuple[int, str, int, int | None]],
) -> list[tuple[int, str, int, int | None]]:
    """Revenue lines are credits (negative); expense lines debits (positive)."""
    return [(t, a, -x if TYPES[a] == "revenue" else x, d) for t, a, x, d in lines]


@settings(max_examples=200, deadline=None)
@given(st.lists(line, max_size=60), months(), st.integers(0, 5))
def test_divisions_and_corporate_sum_to_the_company(lines, rows, month) -> None:  # type: ignore[no-untyped-def]
    lines = _signed(lines)
    report = division_report(lines, rows, TYPES, month, month)  # type: ignore[arg-type]
    pnl = profit_and_loss(((t, a, x) for t, a, x, _ in lines), TYPES, month, month)  # type: ignore[arg-type]
    cols = report.columns
    assert sum(c.revenue for c in cols) == pnl.total_revenue == report.company.revenue
    assert report.company.operating_profit == pnl.operating_result  # the real P&L (M10r)
    assert report.company.direct_profit == pnl.operating_result
    assert sum(c.direct_profit for c in cols) == pnl.operating_result
    assert sum(c.operating_profit for c in cols) == pnl.operating_result
    assert sum(c.shared_services for c in cols) == 0  # no cash moves between divisions
    # the allocation spreads exactly the corporate operating costs (corporate keeps the rest)
    corporate_costs = sum(
        x
        for t, a, x, d in lines
        if t == month and d is None and TYPES[a] == "expense" and is_operating_cost(a)
    )
    allocated = -sum(c.shared_services for c in cols if c.division_id is not None)
    assert allocated >= 0
    kept = corporate_costs - allocated
    corporate = cols[0]
    assert corporate.shared_services == allocated
    month_rows = [r for r in rows if r.turn == month]
    central = {r.division_id: r.headcount for r in month_rows if r.division_id and not r.embedded}
    corp_heads = sum(r.headcount for r in month_rows if r.division_id is None)
    expected = allocate_shared(corporate_costs, corp_heads, central)
    assert allocated == sum(expected.values())
    assert kept + allocated == corporate_costs
    embedded = {r.division_id for r in month_rows if r.embedded}
    for c in cols:
        if c.division_id in embedded:
            assert c.shared_services == 0


@settings(max_examples=200, deadline=None)
@given(st.lists(line, max_size=60), months())
def test_every_month_of_a_year_adds_up(lines, rows) -> None:  # type: ignore[no-untyped-def]
    lines = _signed(lines)
    whole = division_report(lines, rows, TYPES, 0, 5)  # type: ignore[arg-type]
    by_month = [division_report(lines, rows, TYPES, m, m) for m in range(6)]  # type: ignore[arg-type]
    for i, col in enumerate(whole.columns):
        assert col.operating_profit == sum(
            next((c.operating_profit for c in r.columns if c.division_id == col.division_id), 0)
            for r in by_month
        ), i
