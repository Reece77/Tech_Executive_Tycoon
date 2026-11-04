"""Research actions (ADR-0014, docs/formulas.md 21.3, 21.5, M11): start and stop a research
project, set its budget, and license research in from a rival or out to one."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.actions.org import active_unit
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InsufficientCashError, ResearchRuleError, UnknownProjectError
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.log import inbox_item
from tst.sim.money import format_money
from tst.sim.research import levels, licensing
from tst.sim.research.formulas import license_price_cents
from tst.sim.research.models import License, ResearchProject
from tst.sim.research.projects import add_lead
from tst.sim.state import GameState, with_license, with_research_project

PERCENT_BP = 100  # tunable-exempt: basis points in a percent, for words


@dataclass(frozen=True, slots=True)
class StartProject:
    actor_id: int
    unit_id: int
    domain: str
    budget_cents: int | None = None  # a month; None = full funding
    kind: Literal["start_project"] = "start_project"


@dataclass(frozen=True, slots=True)
class StopProject:
    actor_id: int
    project_id: int
    kind: Literal["stop_project"] = "stop_project"


@dataclass(frozen=True, slots=True)
class SetProjectBudget:
    actor_id: int
    project_id: int
    budget_cents: int | None  # None = full funding
    kind: Literal["set_project_budget"] = "set_project_budget"


@dataclass(frozen=True, slots=True)
class LicenseIn:
    actor_id: int
    licensor_id: int
    domain: str
    points: float
    kind: Literal["license_in"] = "license_in"


@dataclass(frozen=True, slots=True)
class LicenseOut:
    actor_id: int
    licensee_id: int
    domain: str
    points: float
    kind: Literal["license_out"] = "license_out"


type ResearchAction = StartProject | StopProject | SetProjectBudget | LicenseIn | LicenseOut


def known_domain(data: GameData, domain: str) -> None:
    if domain not in levels.domain_keys(data):
        raise ResearchRuleError(f"unknown research domain {domain!r}")


def own_project(state: GameState, company_id: int, project_id: int) -> ResearchProject:
    project = state.research_project(project_id)
    if project is None or project.company_id != company_id or not project.is_active:
        raise UnknownProjectError(f"no active research project {project_id}")
    return project


def _budget(budget: int | None) -> int | None:
    if budget is not None and budget < 0:
        raise ResearchRuleError("a research budget cannot be negative")
    return budget


def start_project(
    state: GameState, action: StartProject, balance: Balance, data: GameData
) -> Outcome:
    """Immediate, energy 6: an org unit researches a domain. A unit works on one product or
    one project, never both (21.3, 11.3)."""
    company = acting_company(state, action.actor_id)
    known_domain(data, action.domain)
    unit = active_unit(state, company, action.unit_id)
    if unit.product_id is not None:
        product = state.product(unit.product_id)
        name = product.name if product is not None else f"product {unit.product_id}"
        raise ResearchRuleError(f"{unit.name} works on {name}; unassign it first")
    if state.unit_project(unit.id) is not None:
        raise ResearchRuleError(f"{unit.name} already has a research project")
    budget = _budget(action.budget_cents)
    state = spend_energy(
        state, action.actor_id, "start_project", balance, cost=balance.rnd.start_energy
    )
    project_id, ids = state.next_ids.take("research_project")
    project = ResearchProject(
        id=project_id,
        company_id=company,
        domain=action.domain,
        unit_id=unit.id,
        start_turn=state.turn,
        budget_cents=budget,
    )
    return Outcome(with_research_project(replace(state, next_ids=ids), project))


def stop_project(state: GameState, action: StopProject, balance: Balance) -> Outcome:
    """Immediate, energy 2: the unit is free for a product again (21.3)."""
    company = acting_company(state, action.actor_id)
    project = own_project(state, company, action.project_id)
    state = spend_energy(
        state, action.actor_id, "stop_project", balance, cost=balance.rnd.stop_energy
    )
    stopped = replace(project, status="stopped", end_turn=state.turn)
    return Outcome(with_research_project(state, stopped))


def set_project_budget(state: GameState, action: SetProjectBudget, balance: Balance) -> Outcome:
    """Set like a product's marketing budget (21.3): spent in phase 3; below full funding
    output scales by the funded share."""
    company = acting_company(state, action.actor_id)
    project = own_project(state, company, action.project_id)
    budget = _budget(action.budget_cents)
    state = spend_energy(
        state, action.actor_id, "set_project_budget", balance, cost=balance.rnd.budget_energy
    )
    return Outcome(with_research_project(state, replace(project, budget_cents=budget)))


def _rival(state: GameState, rival_id: int) -> int:
    try:
        rival = state.company(rival_id)
    except KeyError:
        raise ResearchRuleError(f"no company {rival_id}") from None
    if rival.is_player or not rival.alive:
        raise ResearchRuleError(f"{rival.name} is not a rival in business")
    return rival.id


def _points(points: float, ceiling: int) -> float:
    """Whole points up to the public ceiling (M12r): the ceiling and every check here use
    only values the player sees, so no answer narrows a rival's lead below its range."""
    if not math.isfinite(points) or points != math.floor(points):
        raise ResearchRuleError("license whole points")
    if points <= 0:
        raise ResearchRuleError("license a positive number of points")
    if points > ceiling:
        raise ResearchRuleError("that is more than the licence allows; ask for fewer points")
    return float(points)


def license_in(
    state: GameState,
    action: LicenseIn,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    """Immediate, energy 8: buy up to (their lead - margin - yours) points from a rival who
    is not a direct competitor, at price_per_point x points x (1 + ARR / $20M), once (21.5)."""
    company = acting_company(state, action.actor_id)
    known_domain(data, action.domain)
    rival = _rival(state, action.licensor_id)
    why = licensing.refusal(state, data, balance, company, rival, action.domain)
    if why is not None:
        raise ResearchRuleError(f"{state.company(rival).name} says no: {why}")
    ceiling = licensing.public_license_in_limit(state, balance, data, company, rival, action.domain)
    points = _points(action.points, ceiling)
    price = license_price_cents(points, licensing.arr_cents(state, company), balance)
    if account_balance(balances, company, CASH) < price:
        raise InsufficientCashError(f"the licence costs {format_money(price)}")
    state = spend_energy(
        state, action.actor_id, "license_in", balance, cost=balance.rnd.license.energy
    )
    label = levels.domain_def(data, action.domain).label
    lic_id, ids = state.next_ids.take("license")
    licence = License(lic_id, rival, company, action.domain, points, state.turn, price)
    state = add_lead(
        with_license(replace(state, next_ids=ids), licence), company, action.domain, points
    )
    log = inbox_item(
        state.turn,
        company,
        "license_in",
        domain=label,
        rival=state.company(rival).name,
        points=f"{points:.1f}",
        price_cents=price,
    )
    entries = licensing.price_entries(state.turn, company, rival, price, label)
    return Outcome(state, entries, (log,))


def license_out(state: GameState, action: LicenseOut, balance: Balance, data: GameData) -> Outcome:
    """Immediate, energy 8: grant a rival up to (your lead - margin - theirs) points; it
    pays royalty_bp of its revenue in the domain's categories each month for royalty_months
    (21.5). Rivals accept any licence that raises their level."""
    company = acting_company(state, action.actor_id)
    known_domain(data, action.domain)
    rival = _rival(state, action.licensee_id)
    ceiling = licensing.public_license_out_limit(
        state, balance, data, company, rival, action.domain
    )
    if ceiling <= 0:
        margin = balance.rnd.license.margin
        raise ResearchRuleError(f"your lead is not more than {margin:g} points ahead of theirs")
    points = _points(action.points, ceiling)
    state = spend_energy(
        state, action.actor_id, "license_out", balance, cost=balance.rnd.license.energy
    )
    lic = balance.rnd.license
    lic_id, ids = state.next_ids.take("license")
    licence = License(
        id=lic_id,
        licensor_id=company,
        licensee_id=rival,
        domain=action.domain,
        points=points,
        turn=state.turn,
        royalty_bp=lic.royalty_bp,
        royalty_end_turn=state.turn + lic.royalty_months - 1,
    )
    state = add_lead(
        with_license(replace(state, next_ids=ids), licence), rival, action.domain, points
    )
    markets = ", ".join(data.category(c).label for c in levels.feeds(data, action.domain))
    log = inbox_item(
        state.turn,
        company,
        "license_out",
        domain=levels.domain_def(data, action.domain).label,
        rival=state.company(rival).name,
        points=f"{points:.1f}",
        royalty=f"{lic.royalty_bp / PERCENT_BP:g}%",
        markets=markets or "no market yet",
        months=lic.royalty_months,
    )
    return Outcome(state, (), (log,))
