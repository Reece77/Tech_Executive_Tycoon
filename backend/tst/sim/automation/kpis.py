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
    # M27b (40.7)
    "device_cover_weeks": "Lowest device cover (weeks)",
    "devices_made": "Devices made last month",
    "supply_cover_pct": "Lowest input cover %",
    "supply_deals": "Supply contracts running",
    "projects": "Exploration projects",
    "exploration_cents": "Exploration committed (12 months)",
    "plants_staffed_pct": "Plants staffed %",
    "plants": "Mines and plants",
    "fab_use_pct": "Fab use %",
    "foundry_share_pct": "Starts under contract %",
    "lobbying_cents": "Lobbying a month",
    "blocked_sales": "Blocked sales",
    "deals_open": "Deals open",
    "targets_screened": "Targets screened",
}
MONEY = frozenset(
    {
        "mrr",
        "marketing_cents",
        "cash_cents",
        "research_cents",
        "exploration_cents",
        "lobbying_cents",
    }
)
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
    company_id: int | None = None,
) -> int:
    company = state.player.id if company_id is None else company_id
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
    return chain_kpi(state, company, key, b, data)


def chain_kpi(state: GameState, company: int, key: str, b: Balance, data: GameData) -> int:
    """M27b's KPIs (40.7), from the company's own rows."""
    from tst.sim.automation import chain

    match key:
        case "device_cover_weeks":
            weeks = [
                chain.cover_weeks(*chain.device_cover(state, pid, b, state.turn))
                for pid in chain.device_products(state, company, b)
            ]
            shown = [w for w in weeks if w is not None]
            return round(min(shown)) if shown else 0
        case "devices_made":
            return round(
                sum(
                    r.units
                    for r in state.production
                    if r.company_id == company
                    and r.product_id in chain.device_products(state, company, b)
                )
            )
        case "supply_cover_pct":
            needs = chain.supply_needs(state, company, b, data)
            return round(min(min(n.cover for n in needs), MAX_COVERAGE) * PCT) if needs else PCT
        case "supply_deals":
            return sum(
                1 for d in state.commodity_deals if d.company_id == company and d.status == "active"
            ) + sum(
                1
                for c in state.production_contracts
                if c.company_id == company and c.status == "active"
            )
        case "projects":
            return sum(
                1
                for p in state.projects
                if p.company_id == company and p.status in ("active", "permitted")
            )
        case "exploration_cents":
            return chain.exploration_spent(state, company)
        case "plants_staffed_pct":
            from tst.sim.facilities.lifecycle import staffing

            kinds = chain._plant_kinds(b) | {"mine"}
            plants = [
                f
                for f in state.company_facilities(company)
                if f.kind in kinds and f.status not in ("closed", "mothballed")
            ]
            if not plants:
                return PCT
            return round(sum(staffing(state, f, b).coverage for f in plants) / len(plants) * PCT)
        case "plants":
            kinds = chain._plant_kinds(b) | {"mine"}
            return sum(
                1
                for f in state.company_facilities(company)
                if f.kind in kinds and f.status != "closed"
            )
        case "fab_use_pct" | "foundry_share_pct":
            months = [
                f.month for f in state.fabs if f.company_id == company and f.month is not None
            ]
            available = sum(m.available for m in months)
            if available <= 0:
                return 0
            if key == "fab_use_pct":
                return round(sum(m.own + m.sold + m.contracted for m in months) / available * PCT)
            return round(sum(m.contracted for m in months) / available * PCT)
        case "lobbying_cents":
            return sum(i.spend_cents for i in state.influence if i.company_id == company)
        case "blocked_sales":
            return len(chain.blocked(state, company, b, data))
        case "deals_open":
            from tst.sim.mna.models import OPEN_DEALS

            return sum(
                1 for d in state.deals if d.acquirer_id == company and d.status in OPEN_DEALS
            )
        case "targets_screened":
            return sum(
                1
                for f in state.target_files
                if f.acquirer_id == company
                and f.diligence_done_turn is not None
                and f.diligence_done_turn <= state.turn
            )
    raise KeyError(key)


def kpi_values(
    state: GameState,
    balances: Mapping[tuple[int, AccountCode], Cents],
    area: str,
    b: Balance,
    data: GameData,
    company_id: int | None = None,
) -> dict[str, int]:
    return {k: kpi_value(state, balances, k, b, data, company_id) for k in area_def(b, area).kpis}


def kpi_target(state: GameState, company: int, key: str, b: Balance) -> int | None:
    fn = TARGETS.get(key)
    return fn(state, company, b) if fn is not None else None
