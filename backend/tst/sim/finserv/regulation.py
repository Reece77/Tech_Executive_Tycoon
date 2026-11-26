"""Bank and insurance regulators (docs/formulas.md 64.5; regulation.yaml `finance_regulators`).

- **Strictness:** a region's bank (or insurance) regulator is strict when its strictness index
  this year is at least `bank.strict_line`; a charter there takes `bank.strict_months` longer.
- **A bank in a tech group** (64.5): each January a player group whose revenue is more than
  `bank.group_review_share` from outside banking and that owns a chartered bank draws its bank
  regulator's review: the bank's dividends to the group are blocked for the year (a regulator may
  block dividends to the parent; the bank's capital is its own).
- **History** (finance_services.yaml regulators.actions): Wells Fargo's asset cap (February 2018 -
  June 2025: its share is held, the data's), Ant Group's halted listing (November 2020), Silicon
  Valley Bank's failure (March 2023: its line closes). They are news for a company in finance in
  their month; a company without finance hears nothing (64.6 target 1).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.finserv.data import file, in_finance
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import times
from tst.sim.state import GameState

JANUARY = 1  # tunable-exempt: calendar


def strictness(state: GameState, region: str, kind: str, data: GameData) -> float:
    year = turn_to_ym(state.turn)[0]
    reg = data.regulation
    if reg is None:
        return 1.0
    values = [
        r.strictness_in(year)
        for r in reg.finance_regulators
        if r.region == region and r.kind == kind
    ]
    return max(values, default=1.0)


def strict(state: GameState, region: str, kind: str, balance: Balance, data: GameData) -> bool:
    return strictness(state, region, kind, data) >= balance.finserv.bank.strict_line


def tech_group(state: GameState, company_id: int, balance: Balance) -> bool:
    """More than `group_review_share` of the company's last month's revenue is not banking."""
    total = 0
    banking = 0
    cat = balance.finserv.banking_category
    for p in state.company_products(company_id):
        rows = [(s.price_cents, s.customers) for s in state.segments_of(p.id)]
        rows += [(r.price_cents, r.customers) for r in state.regional_segments_of(p.id)]
        for price, n in rows:
            month = times(price or 0, n)
            total += month
            if p.category == cat:
                banking += month
    if total <= 0:
        return False
    return (total - banking) / total > balance.finserv.bank.group_review_share  # money-exact: ratio


def group_review_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Each January: chartered banks in tech groups are reviewed (module docstring)."""
    if turn_to_ym(state.turn)[1] != JANUARY or not state.finserv.banks:
        return state, []
    logs: list[LogItem] = []
    banks = []
    for b in state.finserv.banks:
        company = state.company(b.company_id)
        if (
            b.status == "chartered"
            and company is not None
            and company.is_player
            and tech_group(state, b.company_id, balance)
        ):
            b = replace(b, frozen_until=max(b.frozen_until or 0, state.turn + 11))
            logs.append(
                inbox_item(
                    state.turn,
                    b.company_id,
                    "bank_group_review",
                    region=data.region(b.region).label,
                    regulator=file(data).regulators.bank[b.region].name,
                )
            )
        banks.append(b)
    return replace(state, finserv=replace(state.finserv, banks=tuple(banks))), logs


def news_month(state: GameState, balance: Balance, data: GameData) -> list[LogItem]:
    """The data's dated actions as news, in their month, for each player company in finance."""
    out: list[LogItem] = []
    actions = [a for a in file(data).regulators.actions if month_to_turn(a.from_) == state.turn]
    if not actions:
        return out
    for c in state.companies:
        if not c.is_player or not in_finance(state, c.id, balance):
            continue
        for a in actions:
            out.append(inbox_item(state.turn, c.id, "finance_history", text=a.text))
    return out
