"""Turn-phase steps for hiring, payroll, morale and departures (formulas.md sections 6-10).

Each step is pure: state (plus the turn's generators) in, new state, ledger entries and log
items out. People are processed in ascending id order; every random draw comes from its own
stream keyed by the entity it belongs to (ADR-0013).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import replace

from tst.sim.data_models import LEVELS, Balance, GameData
from tst.sim.finance.options import grant_on_hire, retention
from tst.sim.geo.cities import home_city, office_city
from tst.sim.geo.offices import crowded_people, employee_office_cents, rent_lines
from tst.sim.hiring.formulas import (
    ROLL_RANGE,
    acceptance_probability,
    benefits_cents,
    is_lowball,
    market_mid_cents,
    monthly_salary_cents,
    morale_noise_sd,
    morale_step,
    offer_score,
    recruiter_fee_cents,
    resignation_bp,
    retirement_bp,
    roll_succeeds,
)
from tst.sim.hiring.models import Candidate, OfferStatus, PersonState, Search
from tst.sim.hiring.rules import matching_interests, offer_pitch
from tst.sim.ledger import (
    BENEFITS,
    CASH,
    COMPUTE,
    GENERAL_ADMIN,
    MARKETING,
    RECRUITING,
    RENT,
    SALARIES,
    AccountCode,
    LedgerEntry,
    LedgerLine,
    account_balance,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import Cents
from tst.sim.org.divisions import division_of_unit, is_scaleup
from tst.sim.org.morale import morale_terms
from tst.sim.org.rules import is_remote, org_view
from tst.sim.org.scaleup import delegate_energy_factor, support_morale_terms
from tst.sim.people.generator import generate_pool, people_gen_stream
from tst.sim.people.models import Employment, Person
from tst.sim.people.reveal import apply_knowledge_action, new_reveal_state
from tst.sim.products.phases import product_costs_by_division
from tst.sim.rivals.poaching import leave_rival, poach_batch
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    reach_stage,
    with_candidate,
    with_company,
    with_employment,
    with_free_agent,
    with_offer,
    with_person,
    with_person_state,
    with_plan,
    with_reveal,
    with_search,
)

JOB_HOPPER = "job_hopper"
ONE_BATCH = frozenset({"network", "recruiter", "poach"})  # these close after one batch


def _name(person: Person) -> str:
    return f"{person.first_name} {person.last_name}"


def _employees(state: GameState) -> list[tuple[Employment, Person]]:
    """Staff who are not founders, by person id (morale, departures, tag reveals)."""
    pairs = []
    for e in state.employments:
        if e.counts_as_staff:
            person = state.person(e.person_id)
            if not person.is_founder:
                pairs.append((e, person))
    return sorted(pairs, key=lambda pair: pair[1].id)


# --- Phase 1: notices end, offers resolve ---------------------------------------------------


def end_notices(state: GameState) -> tuple[GameState, tuple[LogItem, ...]]:
    """Notice employments become ended in phase 1 of their end_turn (formulas.md section 10)."""
    logs = []
    for e in state.employments:
        if e.status == "notice" and e.end_turn is not None and e.end_turn <= state.turn:
            state = with_employment(state, replace(e, status="ended"))
            person = state.person(e.person_id)
            logs.append(
                inbox_item(
                    state.turn,
                    e.company_id,
                    "employee_left",
                    name=_name(person),
                    reason=e.end_reason or "left",
                )
            )
    return state, tuple(logs)


def _count_plan_hire(
    state: GameState, plan_id: int | None, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """An accepted plan offer counts toward the plan; reaching the target fills it (13.10)."""
    plan = state.plan(plan_id) if plan_id is not None else None
    if plan is None or plan.status == "closed":
        return state, []
    hired = plan.hired + 1
    fills = plan.status == "active" and hired >= plan.target
    state = with_plan(state, replace(plan, hired=hired, status="filled" if fills else plan.status))
    if not fills:
        return state, []
    owner = state.person(plan.owner_id)
    return state, [
        inbox_item(
            state.turn,
            plan.company_id,
            "plan_filled",
            name=_name(owner),
            role=data.role(plan.role).label.lower(),
            target=plan.target,
        )
    ]


def _role_label(person: Person, data: GameData) -> str:
    return data.role(person.role).label.lower() if person.role else "open"


def resolve_offers(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Pending offers resolve in offer-id order (stream hiring, key offer id; section 7)."""
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    hiring = balance.hiring
    for offer in sorted(state.pending_offers_all(), key=lambda o: o.id):
        candidate = state.candidate(offer.candidate_id)
        person = state.person(offer.candidate_id)
        company = state.company(offer.company_id)
        expectation = person.salary_expectation_cents or offer.salary_cents
        ratio = offer.salary_cents / expectation
        gen = rng.stream(state.turn, "hiring", offer.id)
        draw = float(gen.random())
        accepted = False
        if candidate is not None and candidate.status == "open" and not is_lowball(ratio, hiring):
            score = offer_score(
                ratio=ratio,
                equity_bp=offer.equity_bp,
                matching_interests=matching_interests(person, company.mission),
                risk_appetite=person.personality["risk_appetite"],
                ambition=person.personality["ambition"],
                stage=company.stage,
                offer=hiring.offer,
                pitch=offer_pitch(state, offer.actor_id, hiring),
            )
            if candidate.channel == "poach":  # leaving an employer (M5, 15.6)
                score += balance.rivals.poach.leave_penalty
            accepted = draw < acceptance_probability(score, hiring.offer)
        status: OfferStatus = "accepted" if accepted else "declined"
        state = with_offer(state, replace(offer, status=status, resolved_turn=state.turn))
        if candidate is not None:
            state = with_candidate(
                state,
                replace(
                    candidate, status="hired" if accepted else "declined", resolved_turn=state.turn
                ),
            )
        if not accepted:
            logs.append(
                inbox_item(
                    state.turn,
                    company.id,
                    "offer_declined",
                    name=_name(person),
                    role=_role_label(person, data),
                )
            )
            continue
        if candidate is not None and candidate.channel == "poach":
            state = leave_rival(state, person.id, balance, data)  # M5 (15.6)
        emp_id, ids = state.next_ids.take("employment")
        state = replace(state, next_ids=ids)
        joins = state.unit(offer.unit_id) if offer.unit_id is not None else None
        hire = Employment(
            id=emp_id,
            person_id=person.id,
            company_id=company.id,
            role=person.role or "",
            level=person.level or "",
            salary_cents=offer.salary_cents,
            equity_bp=offer.equity_bp,
            start_turn=state.turn,
            end_turn=None,
            status="active",
            unit_id=joins.id if joins is not None and joins.status == "active" else None,
        )
        state = grant_on_hire(with_employment(state, hire), hire)  # options from the pool (14.2)
        state, filled = _count_plan_hire(state, offer.plan_id, data)
        state = with_person_state(
            state, PersonState(person_id=person.id, morale=balance.morale.new_hire)
        )
        # Working together shows interests and work style (M1c review): reveal them at hire.
        reveal = state.reveal(company.id, person.id)
        if reveal is not None and reveal.profile_revealed_turn is None:
            state = with_reveal(state, replace(reveal, profile_revealed_turn=state.turn))
        if candidate is not None and candidate.channel == "recruiter":
            fee = recruiter_fee_cents(offer.salary_cents, hiring)
            if fee:
                units = {u.id: u for u in state.active_units(company.id)}
                d = division_of_unit(units, hire.unit_id)  # the hire's division (M8, 18.1)
                entries.append(
                    LedgerEntry(
                        turn=state.turn,
                        company_id=company.id,
                        memo=f"Recruiter fee: {_name(person)}",
                        lines=(LedgerLine(RECRUITING, fee, d), LedgerLine(CASH, -fee, d)),
                    )
                )
        state, moved = _relocate(state, hire, balance, data)
        entries += moved
        logs.append(
            inbox_item(
                state.turn,
                company.id,
                "offer_accepted",
                link_kind="person",
                link_id=person.id,
                name=_name(person),
                level=person.level or "",
                role=_role_label(person, data),
                salary_cents=offer.salary_cents,
            )
        )
        logs += filled
    return state, tuple(entries), tuple(logs)


# --- Phase 6: payroll and operating costs ---------------------------------------------------


def _relocate(
    state: GameState, hire: Employment, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry]]:
    """A player's hire who lives elsewhere moves to the city they will work in, for
    `hiring.relocation_cents` (6200_recruiting; M9, 19.3). Remote hires stay put."""
    company = state.company(hire.company_id)
    fee = balance.hiring.relocation_cents
    if not company.is_player or not data.cities or is_remote(state, hire):
        return state, []
    person = state.person(hire.person_id)
    city = office_city(state, company.id, hire.unit_id, balance)
    if home_city(person, data) == city:
        return state, []
    state = with_person(state, replace(person, city=city))
    if not fee:
        return state, []
    units = {u.id: u for u in state.active_units(company.id)}
    d = division_of_unit(units, hire.unit_id)
    entry = LedgerEntry(
        turn=state.turn,
        company_id=company.id,
        memo=f"Relocation: {_name(person)} to {data.city(city).label}",
        lines=(LedgerLine(RECRUITING, fee, d), LedgerLine(CASH, -fee, d)),
    )
    return state, [entry]


def monthly_cost_lines(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> tuple[tuple[str, AccountCode, Cents, int | None], ...]:
    """(memo label, account, amount, division id) of one company's phase-6 costs.

    Phase 6 posts exactly these; the Overview shows them as this month's projection (hosting
    at the current customers). Remote staff cost no office fee (formulas.md 13.9); every
    employee but the founder, remote staff included, costs tools and travel (M4c, section 8).
    An employee's salary, benefits, office and tools go to the division containing their
    unit, a product's hosting and marketing to its division; the rest is corporate (None,
    M8, 18.1). A company without divisions has one line per cost, as before M8.
    """
    units = {u.id: u for u in state.active_units(company_id)}
    divisions = [None, *sorted(u.id for u in units.values() if u.kind == "division")]
    staff = state.staff(company_id)

    def division(e: Employment) -> int | None:
        if state.person(e.person_id).is_founder:
            return None
        return division_of_unit(units, e.unit_id)

    salaries: dict[int | None, float] = {d: 0 for d in divisions}
    benefits: dict[int | None, float] = {d: 0 for d in divisions}
    office: dict[int | None, float] = {d: 0 for d in divisions}
    employees: dict[int | None, float] = {d: 0 for d in divisions}
    for e in staff:
        d = division(e)
        salaries[d] += monthly_salary_cents(e.salary_cents)
        benefits[d] += benefits_cents(monthly_salary_cents(e.salary_cents), balance.payroll)
        office[d] += employee_office_cents(state, e, balance, data)  # 8, 19.2 (M9)
        if not state.person(e.person_id).is_founder:
            employees[d] += 1
    job_posts = [s for s in state.open_searches(company_id) if s.channel == "job_post"]
    # A rival's workforce pools cost the same per head at the mid-level rate (M5, 15.1).
    for pool in state.company_pools(company_id):
        role = data.role(balance.rivals.function_roles[pool.function])
        pay = monthly_salary_cents(
            market_mid_cents(role.salary_band_mid_cents["mid"], _mid_region(balance, data))
        )
        salaries[None] += round(pool.headcount * pay)
        benefits[None] += round(pool.headcount * benefits_cents(pay, balance.payroll))
        office[None] += round(pool.headcount * balance.payroll.office_cost_per_head_cents)
        employees[None] += pool.headcount
    hosting, marketing = product_costs_by_division(state, company_id, data)
    tools = balance.costs.tools_per_head_cents
    lines: list[tuple[str, AccountCode, Cents, int | None]] = []
    for memo, account, by_division in (
        ("Salaries", SALARIES, salaries),
        ("Benefits", BENEFITS, benefits),
        ("Office", RENT, office),
        ("Tools and travel", GENERAL_ADMIN, {d: round(tools * n) for d, n in employees.items()}),
    ):
        lines += [(memo, account, int(by_division[d]), d) for d in divisions]
    lines += rent_lines(state, company_id, balance, data)  # leased offices (M9, 19.2)
    lines.append(("Base overhead", GENERAL_ADMIN, balance.company.base_monthly_cost_cents, None))
    lines.append(
        ("Job posts", RECRUITING, balance.hiring.job_post_cost_cents * len(job_posts), None)
    )
    lines += [("Hosting", COMPUTE, hosting.get(d, 0), d) for d in divisions]  # M3 (11.8)
    lines += [("Marketing", MARKETING, marketing.get(d, 0), d) for d in divisions]
    if len(divisions) > 1:
        lines = [(m, a, x, d) for m, a, x, d in lines if x or d is None]
    return tuple(lines)


def monthly_costs(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> tuple[tuple[str, AccountCode, Cents], ...]:
    """(memo label, account, amount) of one company's phase-6 costs, summed over divisions."""
    totals: dict[tuple[str, AccountCode], Cents] = {}
    for memo, account, amount, _ in monthly_cost_lines(state, company_id, balance, data):
        totals[(memo, account)] = totals.get((memo, account), 0) + amount
    return tuple((memo, account, amount) for (memo, account), amount in totals.items())


def _mid_region(balance: Balance, data: GameData) -> int:
    """Pools are paid at the default region's rate (15.1)."""
    return data.region(balance.founder.default_region).salary_multiplier_bp


def employment_monthly_cost_cents(
    employment: Employment,
    balance: Balance,
    *,
    remote: bool = False,
    office_cents: Cents | None = None,
) -> Cents:
    """Salary, benefits and office for one employment per month (formulas.md section 8).

    Remote staff cost no office fee (13.9). `office_cents`: the seat's cost where they work
    (M9, 19.2: flexible space at the HQ's rent index, none in a leased office).
    """
    salary = monthly_salary_cents(employment.salary_cents)
    if office_cents is None:
        office_cents = balance.payroll.office_cost_per_head_cents
    office = 0 if remote else office_cents
    return salary + benefits_cents(salary, balance.payroll) + office


def payroll(
    state: GameState, balance: Balance, data: GameData
) -> tuple[tuple[LedgerEntry, ...], dict[int, Cents]]:
    """Salaries, benefits, office, base overhead, job-post fees, hosting and marketing
    (formulas.md sections 8 and 11.8).

    Returns the entries and, per company, payroll (salaries plus benefits) for the snapshot.
    """
    entries: list[LedgerEntry] = []
    payroll_by_company: dict[int, Cents] = {}
    for company in state.ledger_companies():  # incumbents have no ledger until M5
        costs = monthly_costs(state, company.id, balance, data)
        payroll_by_company[company.id] = sum(
            amount for _, account, amount in costs if account in (SALARIES, BENEFITS)
        )
        lines = [
            LedgerLine(account, amount, division)
            for _, account, amount, division in monthly_cost_lines(state, company.id, balance, data)
            if amount
        ]
        total = sum(line.amount for line in lines)
        if total:
            entries.append(
                LedgerEntry(
                    turn=state.turn,
                    company_id=company.id,
                    memo="Monthly costs: " + ", ".join(memo for memo, _, amount in costs if amount),
                    lines=(*lines, LedgerLine(CASH, -total)),
                )
            )
    return tuple(entries), payroll_by_company


# --- Phase 8: morale, departures, tag reveals, knowledge -----------------------------------


def morale_and_departures(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    opening: Mapping[tuple[int, AccountCode], Cents],
    current: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Morale update (stream morale), then resignation (resign) or retirement (retire) rolls
    for active employees, by person id. The founder is excluded (formulas.md sections 9-10).

    The M2 terms (manager, teammates, remote; section 13) use the reporting lines at the start
    of the phase.
    """
    logs: list[LogItem] = []
    morale_cfg = balance.morale
    views = {c.id: org_view(state, c.id) for c in state.companies}
    supports = {  # W_support by person (M8, 18.4), from the pools at the phase start
        c.id: support_morale_terms(state, views[c.id], balance, data) for c in state.companies
    }
    crowds = {c.id: crowded_people(state, c.id) for c in state.companies}  # M9 (19.2)
    for employment, person in _employees(state):
        company = state.company(employment.company_id)
        target = morale_terms(
            state,
            views[company.id],
            employment,
            balance,
            data,
            account_balance(opening, company.id, CASH),
            account_balance(current, company.id, CASH),
            supports[company.id],
            crowds[company.id],
        ).target
        ps = state.person_state(person.id)
        start = morale_cfg.new_hire if ps.morale is None else ps.morale
        gen = rng.stream(state.turn, "morale", person.id)
        noise = float(
            gen.normal(0.0, morale_noise_sd(person.personality["temperament"], morale_cfg))
        )
        morale = morale_step(start, target, noise, morale_cfg)
        state = with_person_state(state, replace(ps, morale=morale))

        if employment.status != "active":
            continue
        resign_gen = rng.stream(state.turn, "resign", person.id)
        chance = resignation_bp(
            morale,
            person.personality["loyalty"],
            JOB_HOPPER in person.tags,
            balance.resign,
            retention=retention(state, employment, balance),  # unvested options (M4, 14.2)
        )
        reason: str | None = None
        if roll_succeeds(int(resign_gen.integers(0, ROLL_RANGE)), chance):
            reason = "resigned"
        else:
            retire_gen = rng.stream(state.turn, "retire", person.id)
            chance = retirement_bp(person.age(state.turn), balance.people)
            if chance and roll_succeeds(int(retire_gen.integers(0, ROLL_RANGE)), chance):
                reason = "retired"
        if reason is None:
            continue
        state = with_employment(
            state,
            replace(
                employment,
                status="notice",
                end_turn=state.turn + 1,
                end_reason=reason,  # type: ignore[arg-type]
            ),
        )
        logs.append(
            inbox_item(
                state.turn,
                company.id,
                reason,
                link_kind="person",
                link_id=person.id,
                name=_name(person),
            )
        )
    return state, tuple(logs)


def monthly_tag_reveals(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Each hidden tag of an employee reveals to the employer at reveal_bp_per_month
    (stream tags, key person id; one roll per still-hidden tag, in the person's tag order)."""
    logs: list[LogItem] = []
    for employment, person in _employees(state):
        reveal = state.reveal(employment.company_id, person.id)
        if reveal is None or not person.tags:
            continue
        known = {t for t, _ in reveal.revealed_tags}
        hidden = [t for t in person.tags if t not in known]
        if not hidden:
            continue
        gen = rng.stream(state.turn, "tags", person.id)
        found = [
            t
            for t in hidden
            if roll_succeeds(int(gen.integers(0, ROLL_RANGE)), balance.tags.reveal_bp_per_month)
        ]
        if not found:
            continue
        state = with_reveal(
            state,
            replace(
                reveal, revealed_tags=reveal.revealed_tags + tuple((t, state.turn) for t in found)
            ),
        )
        logs += [
            inbox_item(
                state.turn,
                employment.company_id,
                "tag_revealed",
                link_kind="person",
                link_id=person.id,
                name=_name(person),
                reveal_text=next(x.reveal_text for x in data.tags if x.key == t),
            )
            for t in found
        ]
    return state, tuple(logs)


def employed_month(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Working together narrows every staff member's ranges (employed_month, section 4).

    The scout is the company's best true judgment_of_talent among active staff.
    """
    skill_keys = frozenset(data.skill_keys)
    for company in sorted(state.companies, key=lambda c: c.id):
        staff = state.staff(company.id)
        active = [state.person(e.person_id) for e in staff if e.status == "active"]
        if not active:
            continue
        scout = max(p.skills["judgment_of_talent"] for p in active)
        for e in sorted(staff, key=lambda e: e.person_id):
            reveal = state.reveal(company.id, e.person_id)
            if reveal is None:
                continue
            state = with_reveal(
                state,
                apply_knowledge_action(
                    reveal, "employed_month", scout, balance, turn=state.turn, skill_keys=skill_keys
                ),
            )
    return state


# --- Phase 10: stage -----------------------------------------------------------------------


def first_hire_stage(state: GameState) -> GameState:
    """Stage 0 -> 1 once the company has hired anyone other than its founder (spec section 3)."""
    for company in state.companies:
        if company.stage != 0:
            continue
        hired = any(
            e.company_id == company.id and not state.person(e.person_id).is_founder
            for e in state.employments
        )
        if hired:
            state = with_company(state, reach_stage(company, 1, state.turn))
    return state


# --- Phase 12: candidate expiry and new batches --------------------------------------------


def expire_candidates(state: GameState) -> GameState:
    """Open candidates without a pending offer leave in phase 12 of their expires_turn; so do
    free agents (M6 sub-task 0)."""
    for agent in state.free_agents:
        if agent.status == "available" and agent.until_turn <= state.turn:
            state = with_free_agent(state, replace(agent, status="expired"))
    for candidate in state.candidates:
        if (
            candidate.status == "open"
            and candidate.expires_turn <= state.turn
            and state.pending_offer_for(candidate.person_id) is None
        ):
            state = with_candidate(
                state, replace(candidate, status="expired", resolved_turn=state.turn)
            )
    return state


def candidate_batches(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Each open search produces a batch (stream people_gen, key search id; section 7).

    Draw order in the search's generator: batch size, then one level per candidate (level_mix
    weights in LEVELS order), then the people themselves (generate_pool). Network and recruiter
    searches close after their batch.
    """
    logs: list[LogItem] = []
    skill_keys = frozenset(data.skill_keys)
    for search in sorted(state.searches, key=lambda s: s.id):
        if search.status != "open":
            continue
        gen = people_gen_stream(rng, state.turn, search.id)
        if search.channel == "poach":  # a rival's key people, not generated (M5, 15.6)
            state, count = poach_batch(state, search, gen, balance, data)
            state = with_search(state, replace(search, status="closed", closed_turn=state.turn))
            logs.append(
                inbox_item(
                    state.turn,
                    search.company_id,
                    "candidates_arrived",
                    link_kind="search",
                    link_id=search.id,
                    count=count,
                    role=data.role(search.role).label,
                    channel=f"poach from {state.company(search.rival_id or 0).name}",
                    shelf=balance.hiring.candidate_shelf_turns,
                )
            )
            continue
        channel = balance.hiring.channel[search.channel]
        count = int(gen.integers(int(channel.size.lo), int(channel.size.hi), endpoint=True))
        actor = _actor(state, search)
        if (
            actor is not None
            and channel.sociability_bonus
            and (actor.personality["sociability"] >= channel.sociability_threshold)
        ):
            count += channel.sociability_bonus
        levels_keys = [lv for lv in LEVELS if lv in channel.level_mix]
        weights = [channel.level_mix[lv] for lv in levels_keys]
        total = sum(weights)
        levels = [
            levels_keys[int(gen.choice(len(levels_keys), p=[w / total for w in weights]))]
            for _ in range(count)
        ]
        if search.level is not None:  # an exec-level search (M8, 18.3); draws unchanged
            levels = [search.level] * count
        first, ids = state.next_ids.take_many("person", count)
        state = replace(state, next_ids=ids)
        role = data.role(search.role)
        people = generate_pool(
            gen, data, balance, state.turn, role, levels, first_person_id=first, city=search.city
        )
        scout = actor.skills["judgment_of_talent"] if actor is not None else 0.0
        for person in people:
            state = with_person(state, person)
            state = with_candidate(
                state,
                Candidate(
                    person_id=person.id,
                    company_id=search.company_id,
                    search_id=search.id,
                    channel=search.channel,
                    created_turn=state.turn,
                    expires_turn=state.turn + balance.hiring.candidate_shelf_turns,
                ),
            )
            reveal = new_reveal_state(
                observer_company_id=search.company_id,
                person=person,
                turn=state.turn,
                rng=rng,
                data=data,
                balance=balance,
            )
            for action in channel.knowledge:
                reveal = apply_knowledge_action(
                    reveal, action, scout, balance, turn=state.turn, skill_keys=skill_keys
                )
            state = with_reveal(state, reveal)
        if search.company_id == state.player.id:
            state, joined = _free_agents_join(state, search, balance)
            count += joined
        if search.channel in ONE_BATCH:
            state = with_search(state, replace(search, status="closed", closed_turn=state.turn))
        logs.append(
            inbox_item(
                state.turn,
                search.company_id,
                "candidates_arrived",
                link_kind="search",
                link_id=search.id,
                count=count,
                role=role.label,
                channel=search.channel.replace("_", " "),
                shelf=balance.hiring.candidate_shelf_turns,
            )
        )
    return state, tuple(logs)


def _free_agents_join(state: GameState, search: Search, balance: Balance) -> tuple[GameState, int]:
    """Free agents for the search's role join its batch, by person id (M6 sub-task 0)."""
    joined = 0
    for agent in state.free_agents:
        if agent.status != "available" or agent.role != search.role:
            continue
        state = with_free_agent(state, replace(agent, status="placed"))
        if state.candidate(agent.person_id) is not None:
            continue
        state = with_candidate(
            state,
            Candidate(
                person_id=agent.person_id,
                company_id=search.company_id,
                search_id=search.id,
                channel=search.channel,
                created_turn=state.turn,
                expires_turn=state.turn + balance.hiring.candidate_shelf_turns,
            ),
        )
        joined += 1
    return state, joined


def _actor(state: GameState, search: Search) -> Person | None:
    for person in state.people:
        if person.id == search.actor_id:
            return person
    return None


def reset_energy(state: GameState, balance: Balance, data: GameData | None = None) -> GameState:
    """Founder and delegate energy reset after phase 12 for the new month (ADR-0014, 0015).
    From stage 3 a delegate's energy is x the coverage c of their support pool (M8, 18.4)."""
    founders = {p.id for p in state.people if p.is_founder}
    player = state.player
    view = org_view(state, player.id) if data and is_scaleup(player, balance) else None
    for ps in state.person_states:
        if ps.energy is not None:
            cap = (
                balance.founder.energy_per_month
                if ps.person_id in founders
                else balance.delegates.energy_per_month
            )
            delegate = ps.person_id not in founders
            if view is not None and data is not None and delegate and ps.person_id in view.unit_of:
                factor = delegate_energy_factor(state, view, ps.person_id, balance, data)
                cap = math.floor(cap * factor)
            state = with_person_state(state, replace(ps, energy=cap))
    return state
