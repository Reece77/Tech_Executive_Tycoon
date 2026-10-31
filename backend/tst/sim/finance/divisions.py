"""Division statements derived from the ledger (docs/formulas.md 18.1, M8). They add no
state and move no cash.

Each ledger line carries a division id (None = corporate). A division's statement is its
revenue minus its direct costs, then a shared-services allocation: each month, corporate's
operating costs x h_div / (h_corporate + sum h_central) for every central division, from
that month's headcounts. Corporate shows the allocations as a positive line, so divisions
and corporate always add up to the company's statement.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from tst.sim.data_models import AccountType
from tst.sim.ledger import BENEFITS, COMPUTE, MARKETING, RENT, SALARIES, AccountCode
from tst.sim.money import Cents
from tst.sim.org.formulas import allocate_shared
from tst.sim.snapshot import DivisionMonth

COST_OF_REVENUE_PREFIX = "5"

type DivisionLines = Iterable[tuple[int, AccountCode, Cents, int | None]]


@dataclass(slots=True)
class DivisionStatement:
    division_id: int | None  # None: corporate
    name: str
    embedded: bool = False
    revenue: Cents = 0
    salaries_benefits: Cents = 0
    hosting: Cents = 0
    marketing: Cents = 0
    office: Cents = 0
    tools_ga: Cents = 0  # tools, travel, recruiting and every other cost
    shared_services: Cents = 0  # negative for a central division, positive for corporate
    headcount: int = 0  # at the period's last month

    @property
    def costs(self) -> Cents:
        return self.salaries_benefits + self.hosting + self.marketing + self.office + self.tools_ga

    @property
    def direct_profit(self) -> Cents:
        return self.revenue - self.costs

    @property
    def operating_profit(self) -> Cents:
        return self.direct_profit + self.shared_services


@dataclass(slots=True)
class DivisionReport:
    first_turn: int
    last_turn: int
    columns: list[DivisionStatement] = field(default_factory=list)  # corporate first
    company: DivisionStatement = field(default_factory=lambda: DivisionStatement(None, "Company"))


def is_operating_cost(account: AccountCode) -> bool:
    """Operating costs: every expense but hosting and cost of goods (14.1 classification)."""
    return account != COMPUTE and not account.startswith(COST_OF_REVENUE_PREFIX)


def _add(st: DivisionStatement, account: AccountCode, kind: AccountType, amount: Cents) -> None:
    if kind == "revenue":
        st.revenue -= amount
    elif kind != "expense":
        return
    elif account in (SALARIES, BENEFITS):
        st.salaries_benefits += amount
    elif account == COMPUTE:
        st.hosting += amount
    elif account == MARKETING:
        st.marketing += amount
    elif account == RENT:
        st.office += amount
    else:
        st.tools_ga += amount


def allocations(
    corporate_costs: Mapping[int, Cents], months: Iterable[DivisionMonth]
) -> dict[int, dict[int, Cents]]:
    """turn -> central division id -> its allocation that month (18.1)."""
    by_turn: dict[int, list[DivisionMonth]] = {}
    for m in months:
        by_turn.setdefault(m.turn, []).append(m)
    out: dict[int, dict[int, Cents]] = {}
    for turn, rows in by_turn.items():
        corporate = sum(r.headcount for r in rows if r.division_id is None)
        central = {r.division_id: r.headcount for r in rows if r.division_id and not r.embedded}
        out[turn] = allocate_shared(corporate_costs.get(turn, 0), corporate, central)
    return out


def division_report(
    lines: DivisionLines,
    months: Iterable[DivisionMonth],
    types: Mapping[AccountCode, AccountType],
    first_turn: int,
    last_turn: int,
    names: Mapping[int, str] | None = None,
) -> DivisionReport:
    """Every division seen in the period's lines or headcounts, plus corporate and company."""
    months = [m for m in months if first_turn <= m.turn <= last_turn]
    report = DivisionReport(first_turn, last_turn)
    cols: dict[int | None, DivisionStatement] = {None: DivisionStatement(None, "Corporate")}
    for m in sorted(months, key=lambda m: (m.turn, m.division_id or 0)):
        col = cols.setdefault(m.division_id, DivisionStatement(m.division_id, m.name))
        col.name = m.name if m.division_id is not None else col.name
        col.embedded = m.embedded
        col.headcount = m.headcount
    corporate_costs: dict[int, Cents] = {}
    for turn, account, amount, division in lines:
        if not first_turn <= turn <= last_turn:
            continue
        kind = types[account]
        name = (names or {}).get(division or 0, f"Division {division}")
        col = cols.setdefault(division, DivisionStatement(division, name))
        _add(col, account, kind, amount)
        _add(report.company, account, kind, amount)
        if division is None and kind == "expense" and is_operating_cost(account):
            corporate_costs[turn] = corporate_costs.get(turn, 0) + amount
    for shares in allocations(corporate_costs, months).values():
        for division, amount in shares.items():
            cols.setdefault(division, DivisionStatement(division, f"Division {division}"))
            cols[division].shared_services -= amount
            cols[None].shared_services += amount
    report.columns = [cols[None], *(cols[k] for k in sorted(k for k in cols if k is not None))]
    return report
