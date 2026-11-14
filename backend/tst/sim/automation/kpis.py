"""Each area's KPIs for the digest (docs/formulas.md 40.4), from what the company can see: its
own books, staff, products and capacity. Values are integers (percentages and points rounded,
money in cents) so they can be stored with each month's record."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from tst.sim.automation.owners import area_def
from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, AccountCode, account_balance
from tst.sim.money import Cents
from tst.sim.products.models import SELLING
from tst.sim.state import GameState, credibility_of

PCT = 100  # tunable-exempt: percent
MAX_COVERAGE = 9.99  # tunable-exempt: a display cap, as the Org screen shows it
NO_RUNWAY = 99  # tunable-exempt: months shown when the company makes money

LABELS: dict[str, str] = {
    "headcount": "Staff",
    "open_plans": "Open hiring plans",
    "builders": "Builders",
    "products_below_line": "Products with no team",
    "live_products": "Live products",
    "in_development": "In development",
    "mrr": "Monthly revenue",
    "churn_bp": "Customers",
    "marketing_cents": "Marketing a month",
    "brand": "Average brand",
    "coverage_pct": "Support coverage %",
    "cash_cents": "Cash",
    "runway_months": "Runway (months)",
    "research_projects": "Research projects",
    "research_cents": "Research a month",
    "regions": "Regional launches",
    "dc_use_pct": "Data-centre use %",
    "dc_capacity": "Own capacity (CU)",
    "credibility": "Credibility",
    "press_waiting": "Press moments waiting",
    "events_answered": "Events answered this month",
    "events_waiting": "Events waiting",
}
MONEY = frozenset({"mrr", "marketing_cents", "cash_cents", "research_cents"})
# Targets the player has set elsewhere: coverage (the COO's guardrail) and runway (the CFO's).
TARGETS: dict[str, Callable[[GameState, int, Balance], int | None]] = {
    "coverage_pct": lambda s, c, b: round(
        float(dict(b.exec_authority.defaults["coo"])["coverage_target"]) * PCT
    ),
    "runway_months": lambda s, c, b: int(dict(b.exec_authority.defaults["cfo"])["runway_months"]),
}


def _staff(state: GameState, company: int) -> int:
    return sum(1 for e in state.staff(company) if not state.person(e.person_id).is_founder)


def _builders(state: GameState, company: int, data: GameData) -> int:
    return sum(
        1
        for e in state.staff(company)
        if not state.person(e.person_id).is_founder
        and data.role(e.role).product_function == "builder"
    )


def _no_team(state: GameState, company: int) -> int:
    staffed = {u.product_id for u in state.active_units(company) if u.product_id is not None}
    return sum(
        1
        for p in state.company_products(company)
        if p.status in (*SELLING, "in_development") and p.id not in staffed
    )


def _capacity(state: GameState, company: int, b: Balance) -> int:
    from tst.sim.facilities import compute

    return sum(f.live_capacity(state.turn) for f in compute.live_facilities(state, company, b))


def _dc_use(state: GameState, company: int, b: Balance, data: GameData) -> int:
    from tst.sim.facilities import compute

    cap = _capacity(state, company, b)
    if cap <= 0:
        return 0
    need = sum(n.units for n in compute.needs(state, company, b, data))
    return round(need / cap * PCT)


def _coverage(state: GameState, company: int, b: Balance, data: GameData) -> int:
    from tst.sim.org.divisions import support_pools
    from tst.sim.org.rules import org_view

    central = support_pools(state, org_view(state, company), b, data).get(None)
    return round(min(central.coverage, MAX_COVERAGE) * PCT) if central is not None else PCT


def _runway(state: GameState, company: int, cash: Cents, b: Balance, data: GameData) -> int:
    from tst.sim.finance.statements import projected_net_burn

    burn = projected_net_burn(state, company, b, data)
    return NO_RUNWAY if burn <= 0 else min(NO_RUNWAY, int(cash // burn))


def _research_cents(state: GameState, company: int, data: GameData) -> int:
    from tst.sim.research import levels

    return sum(
        p.budget_cents
        if p.budget_cents is not None
        else levels.domain_def(data, p.domain).budget_cents
        for p in state.active_projects(company)
    )


def kpi_value(
    state: GameState,
    balances: Mapping[tuple[int, AccountCode], Cents],
    key: str,
    b: Balance,
    data: GameData,
) -> int:
    company = state.player.id
    products = state.company_products(company)
    live = [p for p in products if p.status in SELLING]
    match key:
        case "headcount":
            return _staff(state, company)
        case "open_plans":
            return sum(1 for p in state.plans if p.company_id == company and p.status == "active")
        case "builders":
            return _builders(state, company, data)
        case "products_below_line":
            return _no_team(state, company)
        case "live_products":
            return len(live)
        case "in_development":
            return sum(1 for p in products if p.status == "in_development")
        case "mrr":
            history = state.company(company).mrr_history
            return int(history[-1]) if history else 0
        case "churn_bp":
            return round(sum(s.customers for p in live for s in state.segments_of(p.id)))
        case "marketing_cents":
            return sum(p.marketing_budget_cents for p in live)
        case "brand":
            return round(sum(p.brand for p in live) / len(live)) if live else 0
        case "coverage_pct":
            return _coverage(state, company, b, data)
        case "cash_cents":
            return account_balance(balances, company, CASH)
        case "runway_months":
            return _runway(state, company, account_balance(balances, company, CASH), b, data)
        case "research_projects":
            return len(state.active_projects(company))
        case "research_cents":
            return _research_cents(state, company, data)
        case "regions":
            return sum(len(state.regions_of(p.id)) for p in products)
        case "dc_use_pct":
            return _dc_use(state, company, b, data)
        case "dc_capacity":
            return _capacity(state, company, b)
        case "credibility":
            cred = credibility_of(state, company)
            return round(cred.value) if cred is not None else 0
        case "press_waiting":
            return sum(1 for e in state.open_events(company) if e.category == "press")
        case "events_answered":
            return sum(
                1
                for d in state.area_decisions
                if d.company_id == company and d.turn == state.turn - 1 and d.kind == "event"
            )
        case "events_waiting":
            return len(state.open_events(company))
    raise KeyError(key)


def kpi_values(
    state: GameState,
    balances: Mapping[tuple[int, AccountCode], Cents],
    area: str,
    b: Balance,
    data: GameData,
) -> dict[str, int]:
    return {k: kpi_value(state, balances, k, b, data) for k in area_def(b, area).kpis}


def kpi_target(state: GameState, company: int, key: str, b: Balance) -> int | None:
    fn = TARGETS.get(key)
    return fn(state, company, b) if fn is not None else None
