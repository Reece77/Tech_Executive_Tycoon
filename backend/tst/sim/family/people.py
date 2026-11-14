"""Family members as people (docs/formulas.md 45.1, 45.3): generating a partner and children
from stream `family`, a child's development each month, and the founder's view of them.

Every draw comes from stream `family` (ADR-0013, id 59): `(head_id, member_index)` for a
member's generation, `(person_id, 1)` for a child's monthly development noise."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

import numpy as np

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.family.models import FAMILY_ROLE, FamilyMember
from tst.sim.people.formulas import growth_delta
from tst.sim.people.generator import draw_name, draw_tags, draw_traits, generate_person
from tst.sim.people.models import PA_KEY, HiddenTraits, Person, Personality, RevealRecord, Skills
from tst.sim.people.reveal import new_reveal_state
from tst.sim.rng import RngFactory
from tst.sim.scale import ABILITY_PER_ATTR, clamp_ability
from tst.sim.state import GameState, with_person, with_reveal

PARTNER_LEVEL: Final = "senior"  # a partner is generated as an experienced adult
DEV_KEY: Final = 1  # stream family's (person_id, 1): a child's development noise
MIN_ADULT: Final = 18  # tunable-exempt: a partner's youngest age
CLOSENESS_BASE: Final = 0.8  # tunable-exempt: 45.3's x (0.8 + 0.4 x closeness / 100)
CLOSENESS_SPAN: Final = 0.4  # tunable-exempt: 45.3's formula constant
SCORE_MAX: Final = 100.0  # tunable-exempt: closeness is 0-100


def family_stream(rng: RngFactory, turn: int, *key: int) -> np.random.Generator:
    """Stream `family` (59), this package's one call site (ADR-0013): `(head_id, index)` a
    member's generation, `(head_id, 0, k)` life events, `(person_id, 1)` development,
    `(head_id, 2)` health, `(head_id, 3, 0)` a CEO search, `(person_id, 4)` an offer refused."""
    return rng.stream(turn, "family", *key)


def member_stream(rng: RngFactory, turn: int, head_id: int, index: int) -> np.random.Generator:
    return family_stream(rng, turn, head_id, index)


def generate_partner(
    gen: np.random.Generator,
    founder: Person,
    turn: int,
    person_id: int,
    balance: Balance,
    data: GameData,
) -> Person:
    """A partner (45.1): an adult person with their own skills, personality and interests,
    near the founder's age, from the founder's region and city."""
    roles = [r for r in data.roles if r.founder_fit]
    role = roles[int(gen.integers(0, len(roles)))]
    person = generate_person(
        gen, data, balance, turn, role, PARTNER_LEVEL, founder.region, person_id=person_id
    )
    age = max(
        MIN_ADULT, founder.age(turn) + round(float(gen.normal(0, balance.family.partner_age_sd)))
    )
    month = int(gen.integers(0, MONTHS_PER_YEAR))
    return replace(
        person,
        role=FAMILY_ROLE,
        level=None,
        salary_expectation_cents=None,
        birth_turn=turn - MONTHS_PER_YEAR * age - month,
        city=founder.city,
    )


def generate_child(
    gen: np.random.Generator,
    parents: tuple[Person, ...],
    age: int,
    turn: int,
    person_id: int,
    balance: Balance,
    data: GameData,
) -> Person:
    """A child (45.1): personality blends the parents' (family.inherit) with their own draw
    and noise; interests come from the parents' and their own; potential is hidden. A child
    older than family.develop_from has grown as development would have made them (no noise)."""
    fb = balance.family
    head = parents[0]
    month = int(gen.integers(0, MONTHS_PER_YEAR)) if age > 0 else 0
    birth = turn - MONTHS_PER_YEAR * age - month
    own = draw_traits(gen, data.personality_keys, balance)
    traits = {}
    for key in data.personality_keys:
        mean = sum(p.personality[key] for p in parents) / len(parents)
        noise = float(gen.normal(0.0, fb.trait_noise_sd))
        traits[key] = fb.inherit * mean + (1 - fb.inherit) * own[key] + noise
    personality = Personality.build(data.personality_keys, traits)
    hidden = HiddenTraits.build(data.hidden_keys, draw_traits(gen, data.hidden_keys, balance))
    base = fb.child_skill_birth + fb.child_skill_year * min(age, fb.develop_from)
    skills = Skills.build(
        data.skill_keys,
        {k: base + float(gen.normal(0.0, fb.child_skill_sd)) for k in data.skill_keys},
    )
    pa = clamp_ability(float(gen.uniform(fb.child_pa.lo, fb.child_pa.hi)))
    interests = _child_interests(gen, parents, balance, data)
    style = parents[int(gen.integers(0, len(parents)))].work_style
    tags = draw_tags(gen, personality, data, balance)
    first, _ = draw_name(gen, head.region, data)
    child = Person(
        id=person_id,
        first_name=first,
        last_name=head.last_name,
        region=head.region,
        birth_turn=birth,
        role=FAMILY_ROLE,
        level=None,
        skills=skills,
        personality=personality,
        hidden=hidden,
        potential_ability=pa,
        interests=interests,
        work_style=style,
        tags=tags,
        salary_expectation_cents=None,
        city=head.city,
    )
    member = FamilyMember(
        person_id=person_id, relation="child", member_index=0, head_id=head.id, joined_turn=turn
    )
    start = birth + MONTHS_PER_YEAR * fb.develop_from
    for t in range(max(start, birth), turn):  # childhood already lived (setup ages)
        child = develop(child, member, t, None, fb.closeness_start, balance, data)
    return child


def _child_interests(
    gen: np.random.Generator, parents: tuple[Person, ...], balance: Balance, data: GameData
) -> tuple[str, ...]:
    span = balance.people.interest_count
    count = int(gen.integers(int(span.lo), int(span.hi), endpoint=True))
    pool = sorted({i for p in parents for i in p.interests}, key=data.interest_keys.index)
    chosen: list[str] = []
    for _ in range(count):
        from_parent = [i for i in pool if i not in chosen]
        others = [i for i in data.interest_keys if i not in chosen]
        u = float(gen.random())
        pick = int(gen.integers(0, 1 << 30))  # tunable-exempt: an index draw
        options = from_parent if from_parent and u < balance.family.parent_interest else others
        if not options:
            break
        chosen.append(options[pick % len(options)])
    return tuple(chosen)


def general_ability(person: Person) -> float:
    """A child's ability across every skill: 10 x the mean skill (as 1's CA scale)."""
    values = [v for _, v in person.skills.items]
    return ABILITY_PER_ATTR * sum(values) / len(values)


def education_mult(
    member: FamilyMember, skill: str, age: int, turn: int, balance: Balance
) -> float:
    """45.3's `e` for one skill this month: the school's from school_age, the university's
    (its degree's skills x degree_mult) until graduate_age, an MBA's on mba_skills."""
    ed = balance.family.education
    e = 1.0
    if ed.school_age <= age < ed.university_age and member.school is not None:
        e = ed.mult[f"school_{member.school}"]
    elif ed.university_age <= age < ed.graduate_age and member.university is not None:
        e = ed.mult[f"uni_{member.university}"]
        if member.degree is not None and skill in ed.degree_skills[member.degree]:
            e *= ed.degree_mult
    if (
        member.mba_turn is not None
        and member.mba_turn <= turn < member.mba_turn + balance.family.mba_months
        and skill in ed.mba_skills
    ):
        e *= ed.mult["mba"]
    return e


def develop(
    person: Person,
    member: FamilyMember,
    turn: int,
    gen: np.random.Generator | None,
    closeness: float,
    balance: Balance,
    data: GameData,
) -> Person:
    """One month of a child's development (45.3): 3's growth formula on every skill toward
    potential, x family.child_growth x e x (0.8 + 0.4 x closeness / 100). `gen` None: no
    noise (a setup child's childhood)."""
    fb = balance.family
    age = person.age(turn)
    if age < fb.develop_from:
        return person
    growth = balance.growth
    ca = general_ability(person)
    prof = person.personality["professionalism"]
    bond = CLOSENESS_BASE + CLOSENESS_SPAN * closeness / SCORE_MAX
    current = person.skills.as_dict()
    changes = {}
    for key in data.skill_keys:
        noise = float(gen.normal(0.0, growth.noise_rel_sd)) if gen is not None else 0.0
        mult = fb.child_growth * education_mult(member, key, age, turn, balance) * bond
        changes[key] = current[key] + growth_delta(
            in_role=True,
            age=age,
            ca=ca,
            pa=person.potential_ability,
            professionalism=prof,
            growth=growth,
            noise=noise,
            mentoring=mult,
        )
    return replace(person, skills=person.skills.updated(changes))


def add_member_person(
    state: GameState, person: Person, rng: RngFactory, balance: Balance, data: GameData
) -> GameState:
    """The person and the player's first view of them (ADR-0007): ranges as for a stranger,
    narrowing with family time (45.3)."""
    state = with_person(state, person)
    reveal = new_reveal_state(
        observer_company_id=state.player.id,
        person=person,
        turn=state.turn,
        rng=rng,
        data=data,
        balance=balance,
    )
    return with_reveal(state, reveal)


def narrow_view(state: GameState, person_id: int, share: float, balance: Balance) -> GameState:
    """The founder's view of a family member narrows: every half-width x (1 - share); the
    potential's never below family.pa_hw_floor (CLAUDE.md 8)."""
    if share <= 0:
        return state
    reveal = state.reveal(state.player.id, person_id)
    if reveal is None:
        return state
    floor = balance.family.pa_hw_floor
    attrs = []
    for key, rec in reveal.attributes:
        hw = rec.hw * (1 - share)
        if key == PA_KEY:
            hw = max(min(rec.hw, floor), hw)
        attrs.append((key, RevealRecord(hw, rec.offset, state.turn)))
    return with_reveal(state, replace(reveal, attributes=tuple(attrs)))
