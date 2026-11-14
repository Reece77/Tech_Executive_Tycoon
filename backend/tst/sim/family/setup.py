"""The Family setting at a new game (docs/formulas.md 45.1): none (the default: no family
record and nothing in this package runs), a partner, or a partner and children of chosen
ages."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidFamilyError
from tst.sim.family.config import SETTINGS
from tst.sim.family.models import CHILD, PARTNER, Family, FamilyMember, Generation
from tst.sim.family.people import add_member_person, generate_child, generate_partner, member_stream
from tst.sim.people.models import Person
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_family, with_family_member, with_person_state

MIN_PARENT_AGE: Final = 18  # tunable-exempt: a parent is at least this much older than a child


@dataclass(frozen=True, slots=True)
class FamilySpec:
    setting: str = "none"  # config.SETTINGS
    child_ages: tuple[int, ...] = ()  # "children": each child's age at the start


NO_FAMILY: Final = FamilySpec()


def check_spec(spec: FamilySpec, founder_age: int, balance: Balance) -> None:
    fb = balance.family
    if spec.setting not in SETTINGS:
        raise InvalidFamilyError(f"family setting must be one of {list(SETTINGS)}")
    if spec.setting != "children" and spec.child_ages:
        raise InvalidFamilyError("children's ages need the 'children' setting")
    if spec.setting == "children":
        if not 1 <= len(spec.child_ages) <= fb.max_children:
            raise InvalidFamilyError(f"choose 1 to {fb.max_children} children")
        for age in spec.child_ages:
            if not fb.start_child_ages.lo <= age <= fb.start_child_ages.hi:
                raise InvalidFamilyError(
                    f"a child's age must be {fb.start_child_ages.lo:.0f}"
                    f"-{fb.start_child_ages.hi:.0f}"
                )
            if age > founder_age - MIN_PARENT_AGE:
                raise InvalidFamilyError(f"a child of {age} needs an older founder")


def start_family(
    state: GameState, spec: FamilySpec, rng: RngFactory, balance: Balance, data: GameData
) -> GameState:
    """The family at the game's start (45.1); the state unchanged for Family none."""
    if spec.setting == "none":
        return state
    founder = state.founder_of(state.player.id)
    if founder is None:
        raise InvalidFamilyError("a family needs a founder")
    check_spec(spec, founder.age(state.turn), balance)
    fb = balance.family
    family = Family(
        id=founder.id,
        setting=spec.setting,
        head_id=founder.id,
        created_turn=state.turn,
        family_time=fb.default_time,
        generations=(Generation(person_id=founder.id, from_turn=state.turn),),
    )
    state = with_family(state, family)
    state, partner = add_partner(state, founder, rng, balance, data, married=True)
    for age in sorted(spec.child_ages, reverse=True):  # the eldest first
        state, _ = add_child(state, (founder, partner), age, rng, balance, data)
    ps = state.person_state(founder.id)
    if ps.energy is not None:  # this month's family time (45.2)
        state = with_person_state(state, replace(ps, energy=max(0, ps.energy - fb.default_time)))
    return state


def _next_index(state: GameState) -> tuple[GameState, int]:
    family = state.family
    assert family is not None
    index = family.next_index
    return with_family(state, replace(family, next_index=index + 1)), index


def add_partner(
    state: GameState,
    founder: Person,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    *,
    married: bool = False,
) -> tuple[GameState, Person]:
    state, index = _next_index(state)
    person_id, ids = state.next_ids.take("person")
    state = replace(state, next_ids=ids)
    gen = member_stream(rng, state.turn, founder.id, index)
    partner = generate_partner(gen, founder, state.turn, person_id, balance, data)
    state = add_member_person(state, partner, rng, balance, data)
    state = with_family_member(
        state,
        FamilyMember(
            person_id=person_id,
            relation=PARTNER,
            member_index=index,
            head_id=founder.id,
            joined_turn=state.turn,
        ),
    )
    family = state.family
    assert family is not None
    state = with_family(
        state,
        replace(
            family,
            relationship=balance.family.relationship_start,
            partner_since=state.turn,
            married=married,
            marriage_asked=married,
            low_months=0,
        ),
    )
    return state, partner


def add_child(
    state: GameState,
    parents: tuple[Person, ...],
    age: int,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, Person]:
    state, index = _next_index(state)
    person_id, ids = state.next_ids.take("person")
    state = replace(state, next_ids=ids)
    head = parents[0]
    gen = member_stream(rng, state.turn, head.id, index)
    child = generate_child(gen, parents, age, state.turn, person_id, balance, data)
    state = add_member_person(state, child, rng, balance, data)
    passed = tuple(m for m in balance.family.milestones if m <= age)
    ed = balance.family.education  # choices already past at the setup: the standard ones
    school = "standard" if age >= ed.school_age else None
    university = "standard" if age >= ed.university_age else None
    state = with_family_member(
        state,
        FamilyMember(
            person_id=person_id,
            relation=CHILD,
            member_index=index,
            head_id=head.id,
            joined_turn=state.turn,
            parent_ids=tuple(p.id for p in parents),
            closeness=balance.family.closeness_start,
            milestones=passed,
            school=school,
            university=university,
        ),
    )
    return state, child
