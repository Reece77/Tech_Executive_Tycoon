"""Statements from ledger lines (formulas.md 14.1) and the projected runway."""

from __future__ import annotations

from tests.helpers import fresh_game, make_person, with_employee, with_product
from tst.loader import LoadedData
from tst.sim.data_models import AccountType
from tst.sim.finance import statements as fs


def types(loaded: LoadedData) -> dict[str, AccountType]:
    return {a.code: a.type for a in loaded.game_data.accounts}


LINES = [
    (0, "1000_cash", 40_000_000),
    (0, "3000_common_equity", -40_000_000),  # starting cash
    (1, "1000_cash", 500_000),
    (1, "4000_revenue_subscriptions", -500_000),  # revenue
    (1, "6300_compute", 40_000),
    (1, "6000_salaries", 2_000_000),
    (1, "1000_cash", -2_040_000),
    (2, "1000_cash", 50_000_000),
    (2, "2600_safes", -50_000_000),  # a SAFE
    (2, "6900_general_admin", 200_000),
    (2, "1000_cash", -200_000),  # its fee
    (3, "2600_safes", 50_000_000),
    (3, "3100_preferred_equity", -50_000_000),  # it converts
]


def test_profit_and_loss(loaded: LoadedData) -> None:
    pnl = fs.profit_and_loss(LINES, types(loaded), 0, 2)
    assert pnl.revenue == {"4000_revenue_subscriptions": 500_000}
    assert pnl.cost_of_revenue == {"6300_compute": 40_000}  # hosting sits under gross margin
    assert pnl.gross_margin == 460_000
    assert pnl.operating_expenses == {"6000_salaries": 2_000_000, "6900_general_admin": 200_000}
    assert (pnl.operating_result, pnl.interest, pnl.tax, pnl.net_result) == (
        -1_740_000,
        0,
        0,
        -1_740_000,
    )


def test_balance_sheet_has_an_accumulated_result(loaded: LoadedData) -> None:
    sheet = fs.balance_sheet(LINES, types(loaded), 2)
    assert sheet.assets == {"1000_cash": 88_260_000}
    assert sheet.liabilities == {"2600_safes": 50_000_000}
    assert sheet.paid_in_equity == {"3000_common_equity": 40_000_000}
    assert sheet.accumulated_result == -1_740_000
    assert sheet.total_assets == sheet.total_liabilities_and_equity
    after = fs.balance_sheet(LINES, types(loaded), 3)
    assert after.liabilities == {"2600_safes": 0}
    assert after.paid_in_equity["3100_preferred_equity"] == 50_000_000


def test_cash_flow(loaded: LoadedData) -> None:
    flow = fs.cash_flow(LINES, types(loaded), 1, 3)
    assert (flow.operating, flow.investing, flow.financing, flow.change_in_cash) == (
        -1_740_000,
        0,
        50_000_000,
        48_260_000,
    )
    assert flow.reconciles
    assert fs.cash_flow(LINES, types(loaded), 3, 3).financing == 0  # conversion moves no cash


def test_period_bounds() -> None:
    assert fs.period_bounds("quarter", 7) == [(0, 2), (3, 5), (6, 7)]
    assert fs.period_bounds("year", 25) == [(0, 11), (12, 23), (24, 25)]
    assert fs.period_bounds("month", 2) == [(0, 0), (1, 1), (2, 2)]


def test_projected_runway_counts_revenue(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    person = make_person(loaded, 2)
    state = with_employee(loaded, state, person, 12_000_000)  # $10,000 + benefits + office
    burn = fs.projected_net_burn(state, 1, loaded.balance, loaded.game_data)
    # salary, benefits, two office fees (the founder's too) and base overhead
    assert burn == 1_000_000 + 200_000 + 2 * 60_000 + 50_000
    assert fs.projected_runway(state, 1, 13_700_000, loaded.balance, loaded.game_data) == 10
    selling = with_product(state, customers={"smb": 1000.0}, prices={"smb": 4000})
    assert fs.projected_net_burn(selling, 1, loaded.balance, loaded.game_data) < 0
    assert fs.projected_runway(selling, 1, 100, loaded.balance, loaded.game_data) is None
