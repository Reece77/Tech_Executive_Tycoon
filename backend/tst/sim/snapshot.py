"""Month-end KPI snapshot per company, persisted to turn_snapshot by the caller."""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.money import Cents


@dataclass(frozen=True, slots=True)
class CompanySnapshot:
    company_id: int
    cash_cents: Cents  # 1000_cash balance at month end
    monthly_burn_cents: Cents  # net cash decrease this month; 0 when cash did not fall
    headcount: int  # active and notice employments, founder included
    payroll_cents: Cents = 0  # salaries plus benefits posted this month (M1b)
    avg_morale: float | None = None  # employees excluding the founder; None if there are none
    mrr_cents: Cents = 0  # this month's revenue (formulas.md 11.8, M3)
    arr_cents: Cents = 0  # 12 x MRR
    founder_bp: int = 0  # the founder's shares in bp of fully diluted shares (M4, 14.2)
    board_confidence: float | None = None  # average director confidence; None without a board

    def kpis(self) -> dict[str, int | float | None]:
        return {
            "cash_cents": self.cash_cents,
            "monthly_burn_cents": self.monthly_burn_cents,
            "headcount": self.headcount,
            "payroll_cents": self.payroll_cents,
            "avg_morale": self.avg_morale,
            "mrr_cents": self.mrr_cents,
            "arr_cents": self.arr_cents,
            "founder_bp": self.founder_bp,
            "board_confidence": self.board_confidence,
        }


@dataclass(frozen=True, slots=True)
class DivisionMonth:
    """Headcount of one division (or corporate, division_id None) at a month's payroll, for
    the shared-services allocation (formulas.md 18.1, M8)."""

    turn: int
    company_id: int
    division_id: int | None
    name: str
    headcount: int
    embedded: bool


@dataclass(frozen=True, slots=True)
class TurnSnapshot:
    turn: int
    companies: tuple[CompanySnapshot, ...]  # sorted by company id

    def for_company(self, company_id: int) -> CompanySnapshot:
        for snap in self.companies:
            if snap.company_id == company_id:
                return snap
        raise KeyError(company_id)


def runway_months(cash_cents: Cents, monthly_burn_cents: Cents) -> int | None:
    """Whole months of cash left at the current burn; None when the company is not burning."""
    if monthly_burn_cents <= 0:
        return None
    return max(cash_cents, 0) // monthly_burn_cents
