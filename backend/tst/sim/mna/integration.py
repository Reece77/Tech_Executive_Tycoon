"""After closing (docs/formulas.md 28.5, M14 sub-task 5): keep the target as a brand
(a company with parent_id, deciding under a directive, its cash swept to the parent) or
integrate it (its products, key people and the pool staff its products need move to the
acquirer; the rest are let go with severance), then 12 months of culture clash.

Monthly draws: stream `integration` (id 38), key (person_id,), for acquired key people's
flight; generated pool staff on stream `people_gen` keyed by the target's stable key."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import MnaRuleError
from tst.sim.events.models import Modifier
from tst.sim.ledger import (
    CASH,
    COMMON_EQUITY,
    INVESTMENT_SUBSIDIARIES,
    SALARIES,
    LedgerBalances,
    LedgerEntry,
    account_balance,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.mna import formulas as mf
from tst.sim.mna.models import AcquiredPerson, Acquisition, Directive
from tst.sim.org.models import OrgUnit
from tst.sim.people.models import Employment
from tst.sim.products import formulas as pf
from tst.sim.products.models import SELLING, Product
from tst.sim.research.models import ResearchLead
from tst.sim.rivals.models import WorkforcePool
from tst.sim.rng import RngFactory
from tst.sim.scale import clamp_morale
from tst.sim.state import (
    GameState,
    with_acquired_person,
    with_acquisition,
    with_company,
    with_employment,
    with_person_state,
    with_product,
    with_research_lead,
    with_unit,
    without_acquired_person,
)

FUNCTIONS = ("builder", "seller", "marketer")
LEVEL_SKILL = (("junior", 8.5), ("mid", 11.5), ("senior", 14.0))  # tunable-exempt: level bands
TOP_LEVEL = "staff"
POOL_STREAM_PART = 38  # tunable-exempt: people_gen sub-key for pool staff kept (28.5)
SKILL_NEUTRAL = 10.0  # tunable-exempt: output = d / 10 (11.3)


@dataclass(frozen=True, slots=True)
class SetDirective:
    """Energy 2: grow, harvest or defend for a kept brand (28.5)."""

    actor_id: int
    company_id: int
    directive: Directive
    kind: Literal["set_directive"] = "set_directive"


def set_directive(state: GameState, action: SetDirective, parent_id: int) -> GameState:
    company = state.company(action.company_id)
    if company.parent_id != parent_id:
        raise MnaRuleError(f"{company.name} is not one of your brands")
    acquisition = next(a for a in reversed(state.acquisitions) if a.target_id == company.id)
    return with_acquisition(state, replace(acquisition, directive=action.directive))


# --- Culture distance ---------------------------------------------------------------------


def _traits(state: GameState, company_id: int, data: GameData) -> dict[str, float]:
    people = [state.person(e.person_id) for e in state.staff(company_id)]
    keys = [t.key for t in data.personality]
    if not people:
        return {}
    return {k: sum(p.personality[k] for p in people) / len(people) for k in keys}


def distance_between(state: GameState, a: int, b: int, balance: Balance, data: GameData) -> float:
    """0-1: the mean gap of the two companies' average personality traits (28.5)."""
    ta, tb = _traits(state, a, data), _traits(state, b, data)
    gaps = [ta[k] - tb[k] for k in ta if k in tb]
    return mf.personality_distance(gaps, balance.integration)


# --- Closing -----------------------------------------------------------------------------


def after_closing(
    state: GameState,
    acquisition: Acquisition,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, Acquisition, list[LedgerEntry], list[LogItem]]:
    """The chosen mode at closing (28.5)."""
    distance = distance_between(
        state, acquisition.acquirer_id, acquisition.target_id, balance, data
    )
    key_people = [e.person_id for e in state.staff(acquisition.target_id)]
    acquisition = replace(acquisition, distance=distance, key_people=len(key_people))
    risky = _risky_person(state, acquisition, key_people)
    until = state.turn + balance.integration.months
    brand = acquisition.mode == "brand"
    tracked = state.company(acquisition.acquirer_id).is_player  # culture clash: the player's
    for pid in key_people if tracked else ():
        mult = balance.mna.problems.key_person_flight_mult if pid == risky else 1.0
        state = with_acquired_person(
            state, AcquiredPerson(pid, acquisition.deal_id, until, brand, mult)
        )
    if brand:
        target = state.company(acquisition.target_id)
        state = with_company(state, replace(target, parent_id=acquisition.acquirer_id))
        return state, replace(acquisition, person_ids=tuple(key_people)), [], []
    return integrate(state, acquisition, rng, balances, balance, data)


def _risky_person(state: GameState, acquisition: Acquisition, people: list[int]) -> int | None:
    """key_person_risk names the target's best-paid key person (28.2; M14 decision)."""
    if "key_person_risk" not in acquisition.problems or not people:
        return None
    pay = {e.person_id: e.salary_cents for e in state.staff(acquisition.target_id)}
    return max(people, key=lambda p: (pay.get(p, 0), -p))


def integrate(
    state: GameState,
    acquisition: Acquisition,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, Acquisition, list[LedgerEntry], list[LogItem]]:
    """Fold the target in (28.5): products and their customers, one new unit per product
    with the key people and the pool staff it needs, severance for the rest, the higher
    research lead plus 20% of the lower, and the churn penalty for 6 months."""
    from tst.sim.rivals.setup import hire_key_people

    ib = balance.integration
    acquirer, target = acquisition.acquirer_id, acquisition.target_id
    company = state.company(target)
    products = [p for p in state.company_products(target) if p.status != "retired"]
    if not state.company(acquirer).is_player:
        return _rival_integrate(state, acquisition, products, balance, data)
    unit_ids: list[int] = []
    for product in products:
        held = product.held_feature
        moved = replace(product, company_id=acquirer)
        if held is not None:  # a static incumbent product starts developing (ADR-0017)
            points = pf.held_feature_points(held, data.category(product.category), state.turn)
            moved = replace(moved, held_feature=None, feature_points=points)
        state = with_product(state, moved)
        unit_id, ids = state.next_ids.take("unit")
        state = with_unit(
            replace(state, next_ids=ids),
            OrgUnit(
                id=unit_id,
                company_id=acquirer,
                kind="team",
                name=f"{product.name} team",
                parent_id=None,
                leader_id=None,
                policy=None,
                created_turn=state.turn,
                product_id=product.id,
            ),
        )
        unit_ids.append(unit_id)
        for months, mult in _churn_penalties(acquisition, balance):
            state = _modifier(state, acquirer, product.id, mult, months)
    key = [e for e in state.staff(target)]
    arrived = [e.person_id for e in key]
    for index, employment in enumerate(sorted(key, key=lambda e: e.id)):
        unit = unit_ids[index % len(unit_ids)] if unit_ids else None
        state = move_person(state, employment, acquirer, unit)
    kept, let_go, severance = 0, 0, 0
    for function in FUNCTIONS:
        pool = next((p for p in state.company_pools(target) if p.function == function), None)
        if pool is None or pool.headcount <= 0:
            continue
        headcount = round(pool.headcount)
        wanted = [
            min(ib.max_per_product, _need(state, p, function, pool.skill, balance, data))
            for p in products
        ]
        keep = min(headcount, sum(wanted))
        level = level_for(pool.skill)
        before = {e.id for e in state.staff(target)}
        state = hire_key_people(
            state,
            state.company(target),
            [function] * keep,
            rng,
            balance,
            data,
            stream_part=POOL_STREAM_PART + FUNCTIONS.index(function),
            levels=[level] * keep,
        )
        new = sorted((e for e in state.staff(target) if e.id not in before), key=lambda e: e.id)
        slots = [unit_ids[i] for i, n in enumerate(wanted) for _ in range(n)]
        for employment, unit in zip(new, slots, strict=False):
            state = move_person(state, employment, acquirer, unit)
            arrived.append(employment.person_id)
        kept += keep
        gone = headcount - keep
        let_go += gone
        role = balance.rivals.function_roles[function]
        from tst.sim.hiring.formulas import market_mid_cents

        mid = data.role(role).salary_band_mid_cents["mid"]
        bp = data.region(balance.founder.default_region).salary_multiplier_bp
        severance += round(
            gone * market_mid_cents(mid, bp) / 12 * ib.severance_months
        )  # tunable-exempt: months a year
        state = _zero_pool(state, pool)
    for lead in [r for r in state.research_leads if r.company_id == target]:
        mine = state.research_lead(acquirer, lead.domain)
        blended = mf.blended_lead(mine, lead.lead, ib)
        state = with_research_lead(state, ResearchLead(acquirer, lead.domain, blended))
    state = with_company(state, replace(company, failed_turn=state.turn))
    acquisition = replace(
        acquisition,
        pool_kept=kept,
        let_go=let_go,
        product_ids=tuple(p.id for p in products),
        unit_ids=tuple(unit_ids),
        person_ids=tuple(arrived),
    )
    entries = []
    if severance > 0:
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=acquirer,
                memo=f"Severance: {let_go} people let go after acquiring {company.name}",
                debit=SALARIES,
                credit=CASH,
                amount=severance,
            )
        )
    return state, acquisition, entries, []


def _rival_integrate(
    state: GameState,
    acquisition: Acquisition,
    products: list[Product],
    balance: Balance,
    data: GameData,
) -> tuple[GameState, Acquisition, list[LedgerEntry], list[LogItem]]:
    """A rival folds in a startup (28.6): its products, key people and pool staff join the
    rival (pools merge, skill weighted by headcount); no severance, no culture clash."""
    acquirer, target = acquisition.acquirer_id, acquisition.target_id
    for product in products:
        state = with_product(state, replace(product, company_id=acquirer))
    for employment in sorted(state.staff(target), key=lambda e: e.id):
        state = move_person(state, employment, acquirer, None)
    kept = 0
    for pool in state.company_pools(target):
        if pool.headcount <= 0:
            continue
        mine = next((p for p in state.company_pools(acquirer) if p.function == pool.function), None)
        if mine is None:
            merged = replace(pool, company_id=acquirer)
        else:
            total = mine.headcount + pool.headcount
            skill = (mine.skill * mine.headcount + pool.skill * pool.headcount) / total
            merged = replace(mine, headcount=total, skill=skill)
        from tst.sim.state import with_pool

        state = with_pool(_zero_pool(state, pool), merged)
        kept += round(pool.headcount)
    for lead in [r for r in state.research_leads if r.company_id == target]:
        mine_lead = state.research_lead(acquirer, lead.domain)
        blended = mf.blended_lead(mine_lead, lead.lead, balance.integration)
        state = with_research_lead(state, ResearchLead(acquirer, lead.domain, blended))
    state = with_company(state, replace(state.company(target), failed_turn=state.turn))
    acquisition = replace(acquisition, pool_kept=kept, product_ids=tuple(p.id for p in products))
    return state, acquisition, [], []


def level_for(skill: float) -> str:
    """The level whose generated skills sit nearest a pool's skill d (M14 decision)."""
    for level, below in LEVEL_SKILL:
        if skill < below:
            return level
    return TOP_LEVEL


def _need(
    state: GameState, product: Product, function: str, skill: float, b: Balance, data: GameData
) -> int:
    """Pool staff a product keeps (28.5): builders to its maintenance line (rot threshold x
    scope of output at the pool's skill); sellers to replace its sales-led customers' churn;
    marketers one per product (M14 decision)."""
    output = max(skill, 1.0) / SKILL_NEUTRAL
    if function == "builder":
        scope = data.category(product.category).scope
        return math.ceil(b.products.rot_threshold * scope / output)
    if function == "seller":
        need = 0.0
        for s in state.segments_of(product.id):
            rate = b.products.seller_rate.get(s.segment)
            if rate:
                need += s.customers * data.segment(s.segment).base_churn / (rate * output)
        return math.ceil(need)
    return 1


def _churn_penalties(acquisition: Acquisition, balance: Balance) -> list[tuple[int, float]]:
    ib, pb = balance.integration, balance.mna.problems
    out = [(ib.churn_months, ib.churn_mult)]
    if "customer_concentration" in acquisition.problems:
        out.append((pb.churn_months, pb.churn_mult))
    return out


def _modifier(
    state: GameState, company_id: int, product_id: int, mult: float, months: int
) -> GameState:
    from tst.sim.state import with_modifier

    mod_id, ids = state.next_ids.take("modifier")
    return with_modifier(
        replace(state, next_ids=ids),
        Modifier(
            id=mod_id,
            company_id=company_id,
            event_id=None,
            target=f"product:{product_id}",
            stat="churn",
            value_pct=(mult - 1) * 100,  # tunable-exempt: percent
            start_turn=state.turn,
            end_turn=state.turn + months,
        ),
    )


def _zero_pool(state: GameState, pool: WorkforcePool) -> GameState:
    pools = tuple(replace(p, headcount=0.0) if p is pool else p for p in state.pools)
    return replace(state, pools=pools)


def move_person(
    state: GameState, employment: Employment, company_id: int, unit_id: int | None
) -> GameState:
    """End the employment at the target and continue it at the acquirer, same role, level
    and pay (28.5)."""
    state = with_employment(
        state, replace(employment, status="ended", end_turn=state.turn, end_reason="acquired")
    )
    # rivals' employments keep the rival id block (from 1,000,001; ADR-0013, migration 0013)
    if state.company(company_id).is_player:
        emp_id, ids = state.next_ids.take("employment")
    else:
        emp_id, ids = state.next_ids.take("rival_employment")
    return with_employment(
        replace(state, next_ids=ids),
        Employment(
            id=emp_id,
            person_id=employment.person_id,
            company_id=company_id,
            role=employment.role,
            level=employment.level,
            salary_cents=employment.salary_cents,
            equity_bp=0,
            start_turn=state.turn,
            end_turn=None,
            status="active",
            unit_id=unit_id,
        ),
    )


# --- Every month --------------------------------------------------------------------------


def integration_month(
    state: GameState,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Phase 7 after closings: brands' cash sweeps; acquired people's flight and culture
    clash; integrated products' brand blend and tech debt (28.2, 28.5)."""
    if not state.acquisitions:
        return state, (), ()
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    entries += _sweeps(state, balances, balance, data)
    state, left = _flight(state, rng, balance)
    logs += left
    state = _clash(state, balance)
    state = _products(state, balance)
    return state, tuple(entries), tuple(logs)


def _sweeps(
    state: GameState, balances: LedgerBalances, balance: Balance, data: GameData
) -> list[LedgerEntry]:
    """A brand's cash above mna.sweep_months of its costs goes to its parent (28.5): the
    brand's equity and the parent's investment fall by the same amount."""
    from tst.sim.mna.deals import monthly_costs_cents

    out = []
    for company in state.companies:
        if company.parent_id is None or not company.alive:
            continue
        closed = max(
            (a.closed_turn for a in state.acquisitions if a.target_id == company.id), default=0
        )
        if closed >= state.turn:  # from the month after closing
            continue
        costs = monthly_costs_cents(state, company.id, balance, data)
        cash = account_balance(balances, company.id, CASH)
        sweep = cash - round(balance.mna.sweep_months * costs)
        if sweep <= 0:
            continue
        out.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=company.id,
                memo=f"Cash swept to {state.company(company.parent_id).name}",
                debit=COMMON_EQUITY,
                credit=CASH,
                amount=sweep,
            )
        )
        out.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=company.parent_id,
                memo=f"Cash swept from {company.name}",
                debit=CASH,
                credit=INVESTMENT_SUBSIDIARIES,
                amount=sweep,
            )
        )
    return out


def _flight(state: GameState, rng: RngFactory, balance: Balance) -> tuple[GameState, list[LogItem]]:
    logs: list[LogItem] = []
    for person in state.acquired_people:
        if state.turn >= person.until_turn:
            state = without_acquired_person(state, person.person_id)
            continue
        employment = state.employment_of(person.person_id)
        acquisition = next(a for a in state.acquisitions if a.deal_id == person.deal_id)
        if acquisition.closed_turn >= state.turn:  # from the month after closing
            continue
        if employment is None or not employment.counts_as_staff:
            state = without_acquired_person(state, person.person_id)
            continue
        chance = mf.flight_chance(acquisition.distance, balance.integration, brand=person.brand)
        u = float(rng.stream(state.turn, "integration", person.person_id).random())
        if u >= min(1.0, chance * person.flight_mult):
            continue
        state = with_employment(
            state, replace(employment, status="ended", end_turn=state.turn, end_reason="resigned")
        )
        state = without_acquired_person(state, person.person_id)
        state = with_acquisition(state, replace(acquisition, departed=acquisition.departed + 1))
        if state.company(acquisition.acquirer_id).is_player:
            p = state.person(person.person_id)
            logs.append(
                inbox_item(
                    state.turn,
                    acquisition.acquirer_id,
                    "deal_update",
                    link_kind="person",
                    link_id=p.id,
                    title=f"{p.first_name} {p.last_name} left after the acquisition",
                    detail=(
                        f"Culture clash after buying "
                        f"{state.company(acquisition.target_id).name}: "
                        f"{acquisition.departed + 1} of {acquisition.key_people} acquired key "
                        "people have left."
                    ),
                )
            )
    return state, logs


def _clash(state: GameState, balance: Balance) -> GameState:
    """Integrated people's morale moves toward the acquirer's average (28.5)."""
    for person in state.acquired_people:
        if person.brand:
            continue
        acquisition = next(a for a in state.acquisitions if a.deal_id == person.deal_id)
        if acquisition.closed_turn >= state.turn:
            continue
        company = acquisition.acquirer_id
        others = [
            state.person_state(e.person_id).morale
            for e in state.staff(company)
            if e.person_id not in {p.person_id for p in state.acquired_people}
        ]
        known = [m for m in others if m is not None]
        ps = state.person_state(person.person_id)
        if not known or ps.morale is None:
            continue
        target = sum(known) / len(known)
        morale = mf.clash_step(ps.morale, target, acquisition.distance, balance.integration)
        state = with_person_state(state, replace(ps, morale=clamp_morale(morale)))
    return state


def _products(state: GameState, balance: Balance) -> GameState:
    """Integrated products: brand toward the acquirer's average; tech debt's quality loss
    spread over its months (28.2, 28.5)."""
    ib, pb = balance.integration, balance.mna.problems
    for acquisition in state.acquisitions:
        if acquisition.mode != "integrate" or not acquisition.product_ids:
            continue
        months = state.turn - acquisition.closed_turn
        if months <= 0:
            continue
        own = [
            p.brand
            for p in state.company_products(acquisition.acquirer_id)
            if p.status in SELLING and p.id not in acquisition.product_ids
        ]
        for pid in acquisition.product_ids:
            product = state.product(pid)
            if product is None or product.company_id != acquisition.acquirer_id:
                continue
            brand = product.brand
            if own:
                brand += ib.brand_blend * (sum(own) / len(own) - brand)
            quality = product.quality
            if "tech_debt" in acquisition.problems and months <= pb.tech_debt_months:
                quality -= pb.tech_debt_quality / pb.tech_debt_months
            state = with_product(
                state,
                replace(product, brand=pf.clamp_score(brand), quality=pf.clamp_score(quality)),
            )
    return state


def subsidiaries_text(state: GameState, parent_id: int) -> str:
    names = [c.name for c in state.companies if c.parent_id == parent_id and c.alive]
    return ", ".join(names) or "none"
