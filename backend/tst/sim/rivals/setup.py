"""Incumbents become rival companies (docs/formulas.md 15.1): personality, workforce pools
sized from revenue, 8 key people, a marketing budget and opening cash.

Used at new game and when an older save is upgraded (migration 0013_rivals). Key people use
stream `people_gen` keyed `(company_id, 0)`: two-part keys never meet a search's one-part key.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import FUNCTIONS, LEVELS, Balance, GameData
from tst.sim.hiring.formulas import benefits_cents, market_mid_cents, monthly_salary_cents
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.people.generator import generate_pool, people_gen_stream
from tst.sim.people.models import Employment
from tst.sim.people.reveal import new_reveal_state
from tst.sim.products.formulas import hosting_cents
from tst.sim.products.models import SELLING
from tst.sim.rivals import formulas as f
from tst.sim.rivals.models import Function, WorkforcePool
from tst.sim.rng import RngFactory
from tst.sim.state import (
    CompanyState,
    GameState,
    with_company,
    with_employment,
    with_person,
    with_person_state,
    with_pool,
    with_product,
    with_reveal,
)

KEY_PEOPLE_STREAM_PART = 0  # tunable-exempt: second key part for incumbent key people
HALF = 0.5  # tunable-exempt: midpoint of each key person's slot in the level spread


def monthly_revenue_cents(state: GameState, company_id: int) -> float:
    """Customers x price over every selling product of the company, this month."""
    total = 0.0
    for product in state.company_products(company_id):
        if product.status not in SELLING:
            continue
        for seg in state.segments_of(product.id):
            total += seg.customers * (seg.price_cents or 0)
    return total


def main_category(state: GameState, company_id: int) -> str | None:
    """The category of the company's biggest product by revenue (its function mix)."""
    best: tuple[float, str] | None = None
    for product in state.company_products(company_id):
        revenue = sum(s.customers * (s.price_cents or 0) for s in state.segments_of(product.id))
        if best is None or revenue > best[0]:
            best = (revenue, product.category)
    return None if best is None else best[1]


def function_mix(state: GameState, company_id: int, balance: Balance) -> dict[str, float]:
    category = main_category(state, company_id)
    mix = balance.rivals.function_mix.get(category or "")
    return dict(mix) if mix else {fn: 1 / len(FUNCTIONS) for fn in FUNCTIONS}


def market_salary_cents(role: str, level: str, balance: Balance, data: GameData) -> int:
    region = data.region(balance.founder.default_region)
    return market_mid_cents(
        data.role(role).salary_band_mid_cents[level], region.salary_multiplier_bp
    )


def loaded_cost_cents(function: str, balance: Balance, data: GameData) -> int:
    """Monthly cost of one pool member: mid-level salary, benefits, office, tools (15.1)."""
    salary = monthly_salary_cents(
        market_salary_cents(balance.rivals.function_roles[function], "mid", balance, data)
    )
    return (
        salary
        + benefits_cents(salary, balance.payroll)
        + balance.payroll.office_cost_per_head_cents
        + balance.costs.tools_per_head_cents
    )


def key_people_split(count: int, mix: dict[str, float]) -> list[str]:
    """`count` functions by largest remainder of the mix, in FUNCTIONS order."""
    exact = {fn: count * mix[fn] for fn in FUNCTIONS}
    whole = {fn: int(exact[fn]) for fn in FUNCTIONS}
    left = count - sum(whole.values())
    for fn in sorted(FUNCTIONS, key=lambda fn: -(exact[fn] - whole[fn]))[:left]:
        whole[fn] += 1
    return [fn for fn in FUNCTIONS for _ in range(whole[fn])]


def _level_for(index: int, count: int, balance: Balance) -> str:
    """Deterministic level spread over key_people_levels (senior first)."""
    levels = [lv for lv in LEVELS if lv in balance.rivals.key_people_levels]
    total = sum(balance.rivals.key_people_levels[lv] for lv in levels)
    point = (index + HALF) / count * total
    acc = 0.0
    for lv in levels:
        acc += balance.rivals.key_people_levels[lv]
        if point < acc:
            return lv
    return levels[-1]


def hire_key_people(
    state: GameState,
    company: CompanyState,
    functions: list[str],
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    *,
    stream_part: int,
    salary_mult: float = 1.0,
    levels: list[str] | None = None,
) -> GameState:
    """Generated individuals employed by the rival, strangers to the player (15.1, 15.5)."""
    gen = people_gen_stream(rng, state.turn, company.id, stream_part)
    for index, function in enumerate(functions):
        role = data.role(balance.rivals.function_roles[function])
        level = levels[index] if levels else _level_for(index, len(functions), balance)
        person_id, ids = state.next_ids.take("rival_person")
        (person,) = generate_pool(
            gen, data, balance, state.turn, role, [level], first_person_id=person_id
        )
        person = replace(person, salary_expectation_cents=None)
        emp_id, ids = ids.take("rival_employment")
        salary = round(market_salary_cents(role.key, level, balance, data) * salary_mult)
        state = replace(with_person(state, person), next_ids=ids)
        state = with_employment(
            state,
            Employment(
                id=emp_id,
                person_id=person.id,
                company_id=company.id,
                role=role.key,
                level=level,
                salary_cents=salary,
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
            ),
        )
        state = with_person_state(
            state, PersonState(person_id=person.id, morale=balance.rivals.pool_morale)
        )
        state = with_reveal(
            state,
            new_reveal_state(
                observer_company_id=state.player.id,
                person=person,
                turn=state.turn,
                rng=rng,
                data=data,
                balance=balance,
            ),
        )
    return state


def opening_cash_cents(state: GameState, company_id: int, data: GameData) -> int:
    """An incumbent's starting cash: the table's months of its revenue (15.1)."""
    company = state.company(company_id)
    spec = next((i for i in data.incumbents if i.name == company.name), None)
    if spec is None or company.is_player or company.is_startup:
        return 0
    return round(monthly_revenue_cents(state, company_id) * spec.cash_months)


def key_people_monthly_cents(state: GameState, company_id: int, balance: Balance) -> int:
    total = 0
    for e in state.staff(company_id):
        salary = monthly_salary_cents(e.salary_cents)
        total += (
            salary
            + benefits_cents(salary, balance.payroll)
            + balance.payroll.office_cost_per_head_cents
            + balance.costs.tools_per_head_cents
        )
    return total


def setup_incumbents(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    """Every incumbent without a personality becomes a rival (15.1)."""
    rv = balance.rivals
    specs = {inc.name: inc for inc in data.incumbents}
    entries: list[LedgerEntry] = []
    for company in state.companies:
        spec = specs.get(company.name)
        if company.is_player or company.is_startup or company.personality or spec is None:
            continue
        company = replace(
            company,
            personality=spec.personality,
            builder_skill=spec.builder_skill,
            target_margin_bp=spec.target_margin_bp,
        )
        state = with_company(state, company)
        revenue = 0.0
        for product in state.company_products(company.id):
            product_revenue = sum(
                s.customers * (s.price_cents or 0) for s in state.segments_of(product.id)
            )
            revenue += product_revenue
            budget = round(product_revenue * rv.start_marketing_share)
            state = with_product(state, replace(product, marketing_budget_cents=budget))
        hosting = 0.0
        for product in state.company_products(company.id):
            category = data.category(product.category)
            year = turn_to_ym(state.turn)[0]
            for seg in state.segments_of(product.id):
                hosting += seg.customers * hosting_cents(
                    category, seg.segment, data.compute_index, year
                )
        marketing = sum(p.marketing_budget_cents for p in state.company_products(company.id))
        mix = function_mix(state, company.id, balance)
        functions = key_people_split(rv.key_people, mix)
        state = hire_key_people(
            state, company, functions, rng, balance, data, stream_part=KEY_PEOPLE_STREAM_PART
        )
        pool_budget = f.pool_budget_cents(revenue, spec.target_margin_bp, hosting, marketing)
        pool_budget = max(0.0, pool_budget - key_people_monthly_cents(state, company.id, balance))
        for function in FUNCTIONS:
            heads = pool_budget * mix[function] / loaded_cost_cents(function, balance, data)
            skill = spec.builder_skill if function == "builder" else rv.pool_skill_other
            fn: Function = function  # type: ignore[assignment]
            state = with_pool(
                state, WorkforcePool(company.id, fn, heads, float(skill), rv.pool_morale)
            )
        cash = opening_cash_cents(state, company.id, data)
        if cash:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=company.id,
                    memo="Opening cash",
                    debit=CASH,
                    credit=COMMON_EQUITY,
                    amount=cash,
                )
            )
    return state, tuple(entries)
