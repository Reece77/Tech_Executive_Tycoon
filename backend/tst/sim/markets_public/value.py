"""Fundamentals behind V_f (docs/formulas.md 25.3): trailing growth and operating margin,
the multiple and V_f itself. Hidden: the API shows only what analysts publish (25.8)."""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.data_models import Balance, GameData
from tst.sim.finance import macro
from tst.sim.finance.captable import fd_shares
from tst.sim.markets_public import formulas as pf
from tst.sim.state import CompanyState, GameState

MONTHS_A_YEAR = 12


@dataclass(frozen=True, slots=True)
class Fundamentals:
    arr_cents: int
    growth: float  # trailing annual revenue growth
    margin: float  # trailing operating margin, a fraction
    multiple: float
    value_cents: int  # V_f
    shares: int  # fully diluted

    @property
    def per_share_cents(self) -> int:
        return pf.per_share_cents(self.value_cents, self.shares)


def trailing(
    company: CompanyState, revenue_now: int, op_now: int, months: int
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The last `months` months' revenue and operating results, this month included."""
    revenue = (*company.mrr_history, revenue_now)[-months:]
    ops = (*company.op_history, op_now)[-months:]
    return revenue, ops


def growth_of(company: CompanyState, revenue_now: int) -> float:
    """Revenue now against a year ago (25.3 g); 0 with no revenue a year ago to compare."""
    history = (*company.mrr_history, revenue_now)
    if len(history) <= MONTHS_A_YEAR:
        return 0.0
    then = history[-MONTHS_A_YEAR - 1]
    return revenue_now / then - 1 if then > 0 else 0.0


def margin_of(company: CompanyState, revenue_now: int, op_now: int) -> float:
    revenue, ops = trailing(company, revenue_now, op_now, MONTHS_A_YEAR)
    total = sum(revenue)
    return sum(ops) / total if total > 0 else 0.0


def fundamentals(
    state: GameState,
    company_id: int,
    revenue_now: int,
    op_now: int,
    balance: Balance,
    data: GameData,
) -> Fundamentals:
    """V_f = ARR x m with m from trailing growth, margin, the base rate and the venture
    climate (25.3)."""
    company = state.company(company_id)
    g = growth_of(company, revenue_now)
    margin = margin_of(company, revenue_now, op_now)
    m = pf.multiple(
        g,
        margin,
        macro.base_rate(state, data),
        macro.venture_climate(state, data),
        balance.public.multiple,
    )
    arr = revenue_now * MONTHS_A_YEAR
    return Fundamentals(
        arr_cents=arr,
        growth=g,
        margin=margin,
        multiple=m,
        value_cents=pf.fundamental_value_cents(arr, m),
        shares=fd_shares(state, company_id),
    )
