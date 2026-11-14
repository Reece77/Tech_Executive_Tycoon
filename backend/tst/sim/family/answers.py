"""The family's choices (docs/formulas.md 45.2-45.5): answers to data/events/family.yaml's
events and the one-offs on the Family screen (family time, education, mentoring, a job in
the group), each applied by the engine."""

from __future__ import annotations

from dataclasses import replace
from statistics import median
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.events.models import GameEvent
from tst.sim.family import rules
from tst.sim.family.config import DEGREES, SCHOOLS, UNIVERSITIES
from tst.sim.family.models import FamilyMember
from tst.sim.family.people import family_stream, narrow_view
from tst.sim.family.steps import FAMILY_STEPS
from tst.sim.founder.models import PERSONAL_CASH, PERSONAL_SPENDING
from tst.sim.founder.personal import cash_cents
from tst.sim.founder.wealth import post
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import LedgerBalances
from tst.sim.log import LogItem, inbox_item
from tst.sim.people.models import Employment
from tst.sim.people.reveal import shown_rating
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    family_member,
    family_partner,
    with_employment,
    with_family,
    with_family_member,
    with_person,
    with_person_state,
)

SCORE_MAX: Final = 100.0  # tunable-exempt: relationship is 0-100
OWN_WAY_KEY: Final = 4  # tunable-exempt: stream key (person_id, 4): an offer refused
COSTS: Final = {  # education choice -> family.education.cents key (None: free)
    ("school", "standard"): None,
    ("school", "elite"): "elite_school",
    ("university", "none"): None,
    ("university", "standard"): "uni_standard",
    ("university", "top"): "uni_top",
    ("mba", "mba"): "mba",
}


def _subject(state: GameState, event: GameEvent) -> FamilyMember | None:
    return family_member(state, event.person_ids[0]) if event.person_ids else None


def family_step(
    state: GameState,
    event: GameEvent,
    step: str,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LogItem]]:
    """A family event's answer (45.2-45.5)."""
    from tst.sim.family import succession

    family = state.family
    if family is None or step not in FAMILY_STEPS:
        return state, []
    fb = balance.family
    logs: list[LogItem] = []
    rng = RngFactory(state.save_meta.master_seed)
    if step == "family_more_time":
        state = with_family(state, replace(family, strain_until=state.turn + fb.strain_months))
    elif step == "family_counselling":
        head = family.head_id
        cost = min(fb.counselling_cents, max(0, cash_cents(state, head)))
        state = post(state, head, "Counselling", "family", PERSONAL_SPENDING, PERSONAL_CASH, cost)
        family = state.family
        assert family is not None
        rel = min(SCORE_MAX, family.relationship + fb.counselling_gain)
        state = with_family(state, replace(family, relationship=rel))
    elif step == "family_carry_on":
        state = with_family(
            state, replace(family, relationship=max(0.0, family.relationship - fb.carry_on_loss))
        )
    elif step == "family_marry":
        if family_partner(state) is not None:
            state = with_family(state, replace(family, married=True))
    elif step == "family_not_yet":
        pass
    elif step.startswith(("family_school_", "family_uni_")) or step == "family_mba":
        member = _subject(state, event)
        if member is not None:
            stage, tier = (
                ("school", step.removeprefix("family_school_"))
                if step.startswith("family_school_")
                else ("mba", "mba")
                if step == "family_mba"
                else ("university", step.removeprefix("family_uni_"))
            )
            try:
                state, log = educate(state, member.person_id, stage, tier, None, balance)
                logs.append(log)
            except InvalidActionError:  # a choice already made, or no cash: a cheaper path
                pass
    elif step == "family_step_back":
        state = succession.open_choice(state, "health", balance)
    elif step == "family_delay":
        delays = family.step_back_delays + 1
        state = with_family(state, replace(family, step_back_delays=delays, step_back_open=False))
        if delays > fb.step_back_delays:  # the third answer is final (45.5)
            state = succession.open_choice(state, "health", balance)
    elif step in ("family_heir", "family_ceo"):
        how = family.succession_open
        if how is None:
            return state, logs
        heirs = rules.eligible_heirs(
            state, balance, "developing" if how == "board" else "not_ready"
        )
        if step == "family_heir" and heirs:
            state, more = succession.hand_to_heir(
                state, heirs[0], how, rng, balances, balance, data
            )
        else:
            state, more = succession.appoint_professional(state, None, how, rng, balance, data)
        logs += more
    return state, logs


def set_family_time(state: GameState, time: int, balance: Balance) -> GameState:
    family = state.family
    if family is None:
        raise InvalidActionError("there is no family")
    if not 0 <= time <= balance.family.max_time:
        raise InvalidActionError(f"family time is 0-{balance.family.max_time} energy a month")
    return with_family(state, replace(family, family_time=time))


def educate(
    state: GameState,
    person_id: int,
    stage: str,
    tier: str,
    degree: str | None,
    balance: Balance,
) -> tuple[GameState, LogItem]:
    """45.3: a school at school_age, a university (with a degree field) at university_age, an
    MBA from mba_from; paid from personal cash once; the reports narrow the founder's view."""
    member = next((m for m in rules.children(state) if m.person_id == person_id), None)
    if member is None:
        raise InvalidActionError(f"person {person_id} is not one of your children")
    ed = balance.family.education
    age = state.person(person_id).age(state.turn)
    if (stage, tier) not in COSTS:
        raise InvalidActionError(f"unknown education {stage} {tier}")
    if stage == "school":
        if tier not in SCHOOLS or member.school is not None:
            raise InvalidActionError("the school is chosen once")
        if not ed.school_age <= age < ed.university_age:
            raise InvalidActionError(f"a school is chosen at {ed.school_age}")
        member = replace(member, school=tier)
    elif stage == "university":
        if tier not in UNIVERSITIES or member.university is not None:
            raise InvalidActionError("the university is chosen once")
        if not ed.university_age <= age < ed.graduate_age:
            raise InvalidActionError(f"a university is chosen at {ed.university_age}")
        if degree is not None and degree not in DEGREES:
            raise InvalidActionError(f"a degree is one of {list(DEGREES)}")
        member = replace(member, university=tier, degree=degree or _degree_for(state, person_id))
    else:
        if member.mba:
            raise InvalidActionError("an MBA is taken once")
        if age < ed.mba_from:
            raise InvalidActionError(f"an MBA is taken from {ed.mba_from}")
        member = replace(member, mba=True, mba_turn=state.turn)
    key = COSTS[(stage, tier)]
    cost = ed.cents[key] if key is not None else 0
    family = state.family
    assert family is not None
    if cost > cash_cents(state, family.head_id):
        raise InvalidActionError("that education needs more personal cash")
    person = state.person(person_id)
    state = post(
        state,
        family.head_id,
        f"Education: {person.first_name}",
        "education",
        PERSONAL_SPENDING,
        PERSONAL_CASH,
        cost,
    )
    state = with_family_member(state, member)
    state = narrow_view(state, person_id, ed.reveal, balance)
    log = inbox_item(
        state.turn,
        state.player.id,
        "family_educated",
        link_kind="person",
        link_id=person_id,
        name=rules.full_name(person),
        stage=stage,
        tier=tier,
        cost_cents=cost,
    )
    return state, log


def _degree_for(state: GameState, person_id: int) -> str:
    """A default degree from the child's interests (engineering unless business, design or
    science interests come first)."""
    by_interest = {
        "ai": "science",
        "hardware": "engineering",
        "security": "engineering",
        "open_source": "engineering",
        "fintech": "business",
        "enterprise": "business",
        "consumer": "business",
        "design": "design",
        "gaming": "design",
        "climate": "science",
        "mining": "science",
    }
    for i in state.person(person_id).interests:
        if i in by_interest:
            return by_interest[i]
    return DEGREES[0]


def set_mentoring(state: GameState, person_id: int, on: bool) -> GameState:
    member = next((m for m in rules.children(state) if m.person_id == person_id), None)
    if member is None:
        raise InvalidActionError(f"person {person_id} is not one of your children")
    if on and rules.in_group(state, person_id) is None:
        raise InvalidActionError("mentoring is for children working in the group")
    return with_family_member(state, replace(member, mentored=on))


def family_energy(state: GameState, balance: Balance) -> int:
    """45.2, 45.4: the month's family time and mentoring, taken from the founder's budget."""
    from tst.sim.family.phase import time_now

    family = state.family
    if family is None:
        return 0
    mentored = sum(1 for m in rules.children(state) if m.mentored)
    return time_now(state, balance) + balance.family.mentor_energy * mentored


def offer_job(
    state: GameState,
    person_id: int,
    company_id: int,
    role: str,
    level: str,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, LogItem]:
    """45.4: from family.join_age a child may join a group company in any role; they accept
    with closeness at least family.join_closeness and a role matching their interests.
    Otherwise they may go their own way (family.own_way_rate)."""
    fb = balance.family
    member = next((m for m in rules.children(state) if m.person_id == person_id), None)
    if member is None:
        raise InvalidActionError(f"person {person_id} is not one of your children")
    person = state.person(person_id)
    if person.age(state.turn) < fb.join_age:
        raise InvalidActionError(f"a child joins from {fb.join_age}")
    if state.employment_of(person_id) is not None:
        raise InvalidActionError(f"{person.first_name} already has a job")
    if company_id not in rules.group_ids(state):
        raise InvalidActionError("that company is not in the group")
    if role not in {r.key for r in data.roles}:
        raise InvalidActionError(f"unknown role {role!r}")
    if level not in balance.people.level_ca:
        raise InvalidActionError(f"unknown level {level!r}")
    name = rules.full_name(person)
    accepts = member.closeness >= fb.join_closeness and rules.roles_match(person, role, data)
    if not accepts:
        rng = RngFactory(state.save_meta.master_seed)
        u = float(family_stream(rng, state.turn, person_id, OWN_WAY_KEY).random())
        if u < fb.own_way_rate and member.own_way is None:
            way = (
                "founded"
                if person.personality["ambition"] >= person.personality["loyalty"]
                else "rival"
            )
            state = with_family_member(state, replace(member, own_way=way))
            from tst.sim.family.phase import _queue_about

            state = _queue_about(state, "family_own_way", person_id)
        log = inbox_item(
            state.turn,
            state.player.id,
            "family_job_declined",
            link_kind="person",
            link_id=person_id,
            name=name,
        )
        return state, log
    salary = _salary(state, role, level, balance, data)
    emp_id, ids = state.next_ids.take("employment")
    state = with_person(state, replace(person, role=role, level=level))
    state = with_employment(
        replace(state, next_ids=ids),
        Employment(
            id=emp_id,
            person_id=person_id,
            company_id=company_id,
            role=role,
            level=level,
            salary_cents=salary,
            equity_bp=0,
            start_turn=state.turn,
            end_turn=None,
            status="active",
        ),
    )
    state = with_person_state(
        state, PersonState(person_id=person_id, morale=balance.morale.new_hire)
    )
    state = with_family_member(
        state, replace(member, company_id=company_id, company_turn=state.turn)
    )
    log = inbox_item(
        state.turn,
        state.player.id,
        "family_joined",
        link_kind="person",
        link_id=person_id,
        name=name,
        company=state.company(company_id).name,
    )
    return state, log


def _salary(state: GameState, role: str, level: str, balance: Balance, data: GameData) -> int:
    """The role's band midpoint at the level (13.8's market rate), regional multiplier 1."""
    mid = data.role(role).salary_band_mid_cents[level]
    step = balance.payroll.salary_round_to_cents
    return round(mid / step) * step


def note_seat(state: GameState, person_id: int, seat: str) -> GameState:
    """An executive seat held, for readiness (45.4)."""
    member = family_member(state, person_id)
    if member is None or seat in member.seats_held:
        return state
    return with_family_member(state, replace(member, seats_held=(*member.seats_held, seat)))


def promotion_reaction(
    state: GameState, person_id: int, old_level: str, balance: Balance, data: GameData
) -> GameState:
    """45.4: staff in the unit see a family member's promotion: morale family.nepotism_morale
    if their displayed fit is below the median of the people passed over (the unit's others at
    the old level or above), family.merit_morale if above."""
    if state.family is None or family_member(state, person_id) is None:
        return state
    from tst.sim.data_models import LEVELS
    from tst.sim.org.rules import org_view

    cid = state.player.id
    view = org_view(state, cid)
    unit = view.unit_of.get(person_id)
    peers = [p for p in view.members.get(unit, ()) if p != person_id]
    person = state.person(person_id)
    if person.role is None or not peers:
        return state
    role = data.role(person.role)
    reveal = state.reveal(cid, person_id)
    if reveal is None:
        return state
    mine = shown_rating(person, reveal, tuple(role.primary))
    passed = []
    for pid in peers:
        e = state.employment_of(pid)
        rev = state.reveal(cid, pid)
        if e is None or rev is None or LEVELS.index(e.level) < LEVELS.index(old_level):
            continue
        other = state.person(pid)
        prim = (
            tuple(data.role(e.role).primary)
            if e.role in {r.key for r in data.roles}
            else tuple(role.primary)
        )
        passed.append(shown_rating(other, rev, prim))
    if not passed:
        return state
    delta = balance.family.nepotism_morale if mine < median(passed) else balance.family.merit_morale
    from tst.sim.actions.org import bump_morale

    for pid in peers:
        state = bump_morale(state, pid, delta)
    return state
