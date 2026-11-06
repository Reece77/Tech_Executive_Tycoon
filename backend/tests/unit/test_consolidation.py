"""M14 (28.5): a kept brand consolidates into its parent's statements, and the group's
balance sheet balances through closing and cash sweeps."""

from __future__ import annotations

from tst.loader import LoadedData
from tst.sim.finance import statements as fs
from tst.sim.finance.consolidation import consolidated_lines
from tst.sim.ledger import CASH, COMMON_EQUITY, GOODWILL, INVESTMENT_SUBSIDIARIES

REV, COST = "4000_revenue_subscriptions", "6000_salaries"


def test_a_brand_consolidates_and_the_group_balances(loaded: LoadedData) -> None:
    types = {a.code: a.type for a in loaded.game_data.accounts}
    # the parent: $1,000 raised, pays $600 at turn 2 for a brand worth $400 (book) + $200 goodwill
    parent = [
        (0, CASH, 1000),
        (0, COMMON_EQUITY, -1000),
        (2, INVESTMENT_SUBSIDIARIES, 400),
        (2, GOODWILL, 200),
        (2, CASH, -600),
        (4, CASH, 150),
        (4, INVESTMENT_SUBSIDIARIES, -150),  # a sweep from the brand
    ]
    # the brand: $400 of equity, earns $300 before closing and $250 after; pays the sweep
    brand = [
        (0, CASH, 400),
        (0, COMMON_EQUITY, -400),
        (1, CASH, 300),
        (1, REV, -300),  # before closing: not the group's
        (2, CASH, -300),
        (2, COMMON_EQUITY, 300),  # a dividend before closing: book 400
        (3, CASH, 250),
        (3, REV, -250),
        (4, COMMON_EQUITY, 150),
        (4, CASH, -150),
    ]
    lines = consolidated_lines(parent, [(brand, 2)], types)
    assert sum(x[2] for x in lines) == 0
    sheet = fs.balance_sheet(lines, types, 4)
    assert sheet.total_assets == sheet.total_liabilities_and_equity
    pnl = fs.profit_and_loss(lines, types, 3, 4)
    assert pnl.total_revenue == 250  # only after closing
    cash = sum(a for t, acc, a in lines if acc == CASH and t <= 4)
    assert cash == 1000 - 600 + 150 + 400 + 250 - 150  # parent's + the brand's, sweep inside
