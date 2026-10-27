"""Statements derived from the ledger (docs/formulas.md 14.1): profit and loss, the balance
sheet with an accumulated result, cash flow, and the projected runway. They add no state.

Lines are (turn, account, amount) with debits positive and credits negative (ADR-0003).
Revenue and liability and equity balances are credits, so they are negated for display.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Literal

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import AccountType, Balance, GameData
from tst.sim.hiring.phases import monthly_costs
from tst.sim.ledger import CASH, COMPUTE, AccountCode
from tst.sim.money import Cents
from tst.sim.products.phases import projected_revenue
from tst.sim.snapshot import runway_months
from tst.sim.state import GameState

type Period = Literal["month", "quarter", "year"]
PERIODS: tuple[Period, ...] = ("month", "quarter", "year")
QUARTER_MONTHS = 3  # tunable-exempt: calendar definition
COST_OF_REVENUE_PREFIX = "5"  # 5xxx cost of goods sold (unused in v1), plus hosting 6300
INTEREST_PREFIX = "7"
TAX_PREFIX = "8"

type Lines = Iterable[tuple[int, AccountCode, Cents]]


@dataclass(frozen=True, slots=True)
class ProfitAndLoss:
    first_turn: int
    last_turn: int
    revenue: Mapping[AccountCode, Cents] = field(default_factory=dict)  # positive
    cost_of_revenue: Mapping[AccountCode, Cents] = field(default_factory=dict)
    operating_expenses: Mapping[AccountCode, Cents] = field(default_factory=dict)
    interest: Cents = 0
    tax: Cents = 0

    @property
    def total_revenue(self) -> Cents:
        return sum(self.revenue.values())

    @property
    def gross_margin(self) -> Cents:
        return self.total_revenue - sum(self.cost_of_revenue.values())

    @property
    def operating_result(self) -> Cents:
        return self.gross_margin - sum(self.operating_expenses.values())

    @property
    def net_result(self) -> Cents:
        return self.operating_result - self.interest - self.tax


@dataclass(frozen=True, slots=True)
class BalanceSheet:
    at_turn: int
    assets: Mapping[AccountCode, Cents]
    liabilities: Mapping[AccountCode, Cents]  # positive
    paid_in_equity: Mapping[AccountCode, Cents]  # positive
    accumulated_result: Cents

    @property
    def total_assets(self) -> Cents:
        return sum(self.assets.values())

    @property
    def total_liabilities_and_equity(self) -> Cents:
        return (
            sum(self.liabilities.values())
            + sum(self.paid_in_equity.values())
            + self.accumulated_result
        )


@dataclass(frozen=True, slots=True)
class CashFlow:
    first_turn: int
    last_turn: int
    operating: Cents  # the net result: no accruals in v1
    investing: Cents  # non-cash assets bought (none in v1)
    financing: Cents  # SAFEs and priced rounds
    change_in_cash: Cents  # the cash account's movement

    @property
    def reconciles(self) -> bool:
        return self.operating + self.investing + self.financing == self.change_in_cash


def _is_pnl(kind: AccountType) -> bool:
    return kind in ("revenue", "expense")


def profit_and_loss(
    lines: Lines, types: Mapping[AccountCode, AccountType], first_turn: int, last_turn: int
) -> ProfitAndLoss:
    revenue: dict[AccountCode, Cents] = {}
    cost: dict[AccountCode, Cents] = {}
    opex: dict[AccountCode, Cents] = {}
    interest = tax = 0
    for turn, account, amount in lines:
        if not first_turn <= turn <= last_turn:
            continue
        kind = types[account]
        if kind == "revenue":
            revenue[account] = revenue.get(account, 0) - amount
        elif kind == "expense":
            if account.startswith(INTEREST_PREFIX):
                interest += amount
            elif account.startswith(TAX_PREFIX):
                tax += amount
            elif account == COMPUTE or account.startswith(COST_OF_REVENUE_PREFIX):
                cost[account] = cost.get(account, 0) + amount
            else:
                opex[account] = opex.get(account, 0) + amount
    return ProfitAndLoss(first_turn, last_turn, revenue, cost, opex, interest, tax)


def balance_sheet(
    lines: Lines, types: Mapping[AccountCode, AccountType], at_turn: int
) -> BalanceSheet:
    """Balances after every entry up to and including `at_turn`. There are no closing
    entries: the accumulated result is the sum of every past net result."""
    assets: dict[AccountCode, Cents] = {}
    liabilities: dict[AccountCode, Cents] = {}
    equity: dict[AccountCode, Cents] = {}
    accumulated = 0
    for turn, account, amount in lines:
        if turn > at_turn:
            continue
        kind = types[account]
        if kind == "asset":
            assets[account] = assets.get(account, 0) + amount
        elif kind == "liability":
            liabilities[account] = liabilities.get(account, 0) - amount
        elif kind == "equity":
            equity[account] = equity.get(account, 0) - amount
        else:
            accumulated -= amount
    return BalanceSheet(at_turn, assets, liabilities, equity, accumulated)


def cash_flow(
    lines: Lines, types: Mapping[AccountCode, AccountType], first_turn: int, last_turn: int
) -> CashFlow:
    operating = investing = financing = change = 0
    for turn, account, amount in lines:
        if not first_turn <= turn <= last_turn:
            continue
        kind = types[account]
        if account == CASH:
            change += amount
        elif _is_pnl(kind):
            operating -= amount
        elif kind == "asset":
            investing -= amount
        else:  # liabilities and equity: SAFE money, rounds, SAFE conversion (net zero)
            financing -= amount
    return CashFlow(first_turn, last_turn, operating, investing, financing, change)


def period_bounds(period: Period, last_turn: int) -> list[tuple[int, int]]:
    """(first, last) turn of every month, quarter or calendar year from turn 0 to last_turn,
    the newest possibly partial. Turn 0 is January 2010, so quarters and years align."""
    size = {"month": 1, "quarter": QUARTER_MONTHS, "year": MONTHS_PER_YEAR}[period]
    return [(start, min(start + size - 1, last_turn)) for start in range(0, last_turn + 1, size)]


def projected_net_burn(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> Cents:
    """This month's projected costs minus this month's revenue at the current customers."""
    costs = sum(amount for _, _, amount in monthly_costs(state, company_id, balance, data))
    return costs - projected_revenue(state, company_id)


def projected_runway(
    state: GameState, company_id: int, cash_cents: Cents, balance: Balance, data: GameData
) -> int | None:
    """Whole months of cash at the projected net burn; None means profitable (14.1)."""
    return runway_months(cash_cents, projected_net_burn(state, company_id, balance, data))
