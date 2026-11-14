"""The family's month (docs/formulas.md 45.1-45.5), run inside phase 12's founder month after
stress. Nothing runs without a Family record (Family none), so those games are unchanged.

Order: family time eases stress and moves the relationship and each child's closeness;
strain and divorce; children develop and the founder's view of them narrows; milestones;
mentored heirs grow; life events (a partner, marriage, children); December's family-control
check; January's health draw from family.step_back_from; the adviser retires at 80."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.family import adviser, rules
from tst.sim.family.models import FamilyMember
from tst.sim.family.people import DEV_KEY, develop, family_stream, narrow_view
from tst.sim.family.setup import add_child, add_partner
from tst.sim.founder import stress
from tst.sim.founder.events import queue
from tst.sim.founder.models import FounderLife
from tst.sim.log import LogItem, inbox_item
from tst.sim.people.formulas import growth_delta
from tst.sim.people.models import current_ability
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    family_partner,
    with_family,
    with_family_member,
    with_life,
    with_person,
)

SCORE_MAX: Final = 100.0  # tunable-exempt: relationship and closeness are 0-100
EVENT_PARTNER: Final = 0  # stream family's (head_id, 0, k) life-event kinds
EVENT_CHILD: Final = 2
HEALTH_KEY: Final = 2  # (head_id, 2): the health step-back draw
JANUARY: Final = 0  # tunable-exempt: calendar (turn % 12)
DECEMBER: Final = 11  # tunable-exempt: calendar (turn % 12)
SCHOOL_TEMPLATE: Final = "family_school"
TEMPLATES_AT_AGE: Final = {"school_age": SCHOOL_TEMPLATE, "university_age": "family_university"}


def time_now(state: GameState, balance: Balance) -> int:
    """This month's family time: the setting, at least family.strain_time while a promise of
    more time holds (45.2)."""
    family = state.family
    if family is None:
        return 0
    if family.strain_until is not None and state.turn < family.strain_until:
        return max(family.family_time, balance.family.strain_time)
    return family.family_time


def bond_delta(time: int, burnt: bool, balance: Balance) -> float:
    """45.2: bond x (time - pivot) / pivot, within +-bond, less burnout_strain a burnout month."""
    fb = balance.family
    raw = fb.bond * (time - fb.bond_pivot) / fb.bond_pivot
    delta = max(-fb.bond, min(fb.bond, raw))
    return delta - (fb.burnout_strain if burnt else 0.0)


def family_month(
    state: GameState,
    life: FounderLife,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, FounderLife, list[LogItem]]:
    family = state.family
    if family is None or family.head_id != life.person_id:
        return state, life, []
    fb = balance.family
    turn, cid = state.turn, state.player.id
    logs: list[LogItem] = []
    time = time_now(state, balance)
    if time:  # 45.2: family time eases stress
        life = stress.add_stress(
            life, turn, -fb.calm * time / fb.max_time, "time with the family", balance.stress
        )
        state = with_life(state, life)
    delta = bond_delta(time, life.burnout, balance)
    partner = family_partner(state)
    if partner is not None:
        state, more = _relationship(state, partner, delta, balance)
        logs += more
    for m in rules.children(state):
        state = _child_month(state, m, delta, time, rng, balance, data)
        state, more = _milestones(state, rules.member_of(state, m.person_id), balance)
        logs += more
    state, more = _life_events(state, rng, balance, data)
    logs += more
    if turn % MONTHS_PER_YEAR == DECEMBER:
        state = rules.check_control(state, balance)
    state, more = _health(state, rng, balance)
    logs += more
    state, more = adviser.adviser_month(state, balance)
    logs += more
    del cid
    return state, life, logs


def _relationship(
    state: GameState, partner: FamilyMember, delta: float, balance: Balance
) -> tuple[GameState, list[LogItem]]:
    from tst.sim.family.divorce import divorce

    fb = balance.family
    family = state.family
    assert family is not None
    rel = max(0.0, min(SCORE_MAX, family.relationship + delta))
    low = family.low_months + 1 if rel < fb.divorce_below else 0
    family = replace(family, relationship=rel, low_months=low)
    state = with_family(state, family)
    logs: list[LogItem] = []
    cooled = family.strain_turn is None or state.turn - family.strain_turn >= fb.strain_cooldown
    if rel < fb.strain_below and cooled:
        state = queue(state, state.player.id, "family_strain", state.turn + 1)
        family = state.family
        assert family is not None
        state = with_family(state, replace(family, strain_turn=state.turn))
    if low >= fb.divorce_months:
        state, more = divorce(state, partner, balance)
        logs += more
    return state, logs


def _child_month(
    state: GameState,
    m: FamilyMember,
    delta: float,
    time: int,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> GameState:
    fb = balance.family
    closeness = m.closeness + delta + (fb.mentor_closeness if m.mentored else 0.0)
    m = replace(m, closeness=max(0.0, min(SCORE_MAX, closeness)))
    state = with_family_member(state, m)
    person = state.person(m.person_id)
    if state.employment_of(m.person_id) is None:  # phase 8 grows them once employed
        gen = family_stream(rng, state.turn, m.person_id, DEV_KEY)
        state = with_person(state, develop(person, m, state.turn, gen, m.closeness, balance, data))
    elif m.mentored:
        state = _mentor_growth(state, m, balance, data)
    return narrow_view(state, m.person_id, fb.reveal_rate * time / fb.max_time, balance)


def _mentor_growth(
    state: GameState, m: FamilyMember, balance: Balance, data: GameData
) -> GameState:
    """45.4: a mentored heir's management and leadership skills grow family.mentor_growth
    more than 3's growth term (no noise, no decline: phase 8 took those)."""
    person = state.person(m.person_id)
    ca = current_ability(person, data)
    age = person.age(state.turn)
    prof = person.personality["professionalism"]
    changes = {}
    for key in balance.family.mentor_skills:
        term = growth_delta(
            in_role=True,
            age=age,
            ca=ca,
            pa=person.potential_ability,
            professionalism=prof,
            growth=balance.growth,
        ) - growth_delta(
            in_role=False,
            age=age,
            ca=ca,
            pa=person.potential_ability,
            professionalism=prof,
            growth=balance.growth,
        )
        changes[key] = person.skills[key] + balance.family.mentor_growth * max(0.0, term)
    return with_person(state, replace(person, skills=person.skills.updated(changes)))


def _milestones(
    state: GameState, m: FamilyMember, balance: Balance
) -> tuple[GameState, list[LogItem]]:
    """45.1: milestones at 5, 12, 18 and 22; 12 and 18 bring the education choices, 22 the
    career one (minor events), and each narrows the founder's view (school reports)."""
    fb = balance.family
    ed = fb.education
    age = state.person(m.person_id).age(state.turn)
    logs: list[LogItem] = []
    for at in fb.milestones:
        if at > age or at in m.milestones:
            continue
        m = replace(m, milestones=(*m.milestones, at))
        state = with_family_member(state, m)
        template = None
        if at == ed.school_age and m.school is None:
            template = SCHOOL_TEMPLATE
        elif at == ed.university_age and m.university is None:
            template = "family_university"
        elif at == fb.join_age:
            template = "family_career"
        if template is not None:
            state = _queue_about(state, template, m.person_id)
        person = state.person(m.person_id)
        logs.append(
            inbox_item(
                state.turn,
                state.player.id,
                "family_milestone",
                link_kind="person",
                link_id=m.person_id,
                name=rules.full_name(person),
                age=at,
            )
        )
    return state, logs


def _queue_about(state: GameState, template: str, person_id: int) -> GameState:
    state = queue(state, state.player.id, template, state.turn + 1)
    q = state.queued[-1]
    return replace(
        state,
        queued=(*state.queued[:-1], replace(q, person_ids=(person_id,))),
    )


def _life_events(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    fb = balance.family
    family = state.family
    assert family is not None
    head = state.person(family.head_id)
    life = None
    from tst.sim.state import life_of

    life = life_of(state, head.id)
    turn, cid = state.turn, state.player.id
    age = head.age(turn)
    logs: list[LogItem] = []
    partner = family_partner(state)
    if partner is None:
        calm = life is None or life.stress < fb.partner_stress_below
        if fb.partner_ages.lo <= age <= fb.partner_ages.hi and calm:
            u = float(family_stream(rng, turn, head.id, 0, EVENT_PARTNER).random())
            if u < fb.partner_rate / MONTHS_PER_YEAR:
                state, person = add_partner(state, head, rng, balance, data)
                logs.append(
                    inbox_item(
                        turn,
                        cid,
                        "family_partner_met",
                        link_kind="person",
                        link_id=person.id,
                        name=rules.full_name(person),
                    )
                )
        return state, logs
    family = state.family
    assert family is not None
    since = family.partner_since if family.partner_since is not None else turn
    if not family.married and not family.marriage_asked and turn - since >= fb.marriage_months:
        state = _queue_about(state, "family_marriage", partner.person_id)
        family = state.family
        assert family is not None
        state = with_family(state, replace(family, marriage_asked=True))
    partner_person = state.person(partner.person_id)
    kids = rules.children(state)
    if partner_person.age(turn) < fb.child_parent_age_max and len(kids) < fb.max_children:
        u = float(family_stream(rng, turn, head.id, 0, EVENT_CHILD).random())
        if u < fb.child_rate / MONTHS_PER_YEAR:
            state, child = add_child(state, (head, partner_person), 0, rng, balance, data)
            logs.append(
                inbox_item(
                    turn,
                    cid,
                    "family_child_born",
                    link_kind="person",
                    link_id=child.id,
                    name=rules.full_name(child),
                )
            )
    return state, logs


def step_back_chance(age: int, balance: Balance) -> float:
    """45.5: family.step_back_rate x (age - 69) a year from family.step_back_from."""
    fb = balance.family
    if age < fb.step_back_from:
        return 0.0
    return min(1.0, fb.step_back_rate * (age - (fb.step_back_from - 1)))


def _health(state: GameState, rng: RngFactory, balance: Balance) -> tuple[GameState, list[LogItem]]:
    """45.5: each January from family.step_back_from, a seeded health event asks the head to
    step back (critical), unless a succession is already open."""
    family = state.family
    assert family is not None
    if state.turn % MONTHS_PER_YEAR != JANUARY or family.step_back_open:
        return state, []
    if family.succession_open is not None:
        return state, []
    head = state.person(family.head_id)
    chance = step_back_chance(head.age(state.turn), balance)
    if not chance:
        return state, []
    u = float(family_stream(rng, state.turn, head.id, HEALTH_KEY).random())
    if u >= chance:
        return state, []
    state = queue(state, state.player.id, "family_step_back", state.turn + 1)
    family = state.family
    assert family is not None
    return with_family(state, replace(family, step_back_open=True)), []
