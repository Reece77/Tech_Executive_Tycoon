"""M10r finding 2 (Codex review 2, P2): loan interest sits below operating profit (20.3), so
division statements leave it out of every operating column and out of the shared-services
allocation (18.1). Office rent is operating: it lowers both statements equally."""

from __future__ import annotations

from tst.loader import LoadedData
from tst.sim.finance.divisions import division_report
from tst.sim.finance.statements import profit_and_loss
from tst.sim.ledger import INTEREST, RENT, REVENUE_SUBSCRIPTIONS
from tst.sim.snapshot import DivisionMonth

PLATFORM = 11
REVENUE, INTEREST_CENTS, BERLIN_RENT = 10_000_000, 3_125_000, 1_012_500
MONTHS = [
    DivisionMonth(0, 1, None, "Corporate", 10, False),
    DivisionMonth(0, 1, PLATFORM, "Platform", 10, False),
]


def _both(loaded: LoadedData, rent: bool) -> tuple[int, int, int, int]:
    types = {a.code: a.type for a in loaded.game_data.accounts}
    lines = [(0, REVENUE_SUBSCRIPTIONS, -REVENUE, None), (0, INTEREST, INTEREST_CENTS, None)]
    if rent:
        lines.append((0, RENT, BERLIN_RENT, None))
    report = division_report(lines, MONTHS, types, 0, 0)
    pnl = profit_and_loss(((t, a, x) for t, a, x, _ in lines), types, 0, 0)
    platform = next(c for c in report.columns if c.division_id == PLATFORM)
    total = sum(c.operating_profit for c in report.columns)
    return pnl.operating_result, report.company.operating_profit, total, platform.operating_profit


def test_interest_is_not_an_operating_cost_of_any_division(loaded: LoadedData) -> None:
    assert _both(loaded, rent=False) == (REVENUE, REVENUE, REVENUE, 0)


def test_rent_lowers_both_statements_and_is_shared(loaded: LoadedData) -> None:
    pnl, company, total, platform = _both(loaded, rent=True)
    assert pnl == company == total == REVENUE - BERLIN_RENT
    assert platform == -BERLIN_RENT // 2  # half the shared rent, none of the interest
