"""Shared family rules (docs/formulas.md 45.4-45.7): who the head's children and heirs are,
readiness from displayed values, and how much of the company the family holds."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.family.config import READINESS
from tst.sim.family.models import CHILD, TRUST_HOLDER, Family, FamilyMember, FamilyNote
from tst.sim.finance.board import average_confidence
from tst.sim.finance.captable import fd_shares
from tst.sim.markets_public.formulas import ceo_score
from tst.sim.money import BP_DENOMINATOR
from tst.sim.people.models import Person
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState, family_member, group_companies, listed_id, with_family

MONTHS_A_YEAR: Final = 12  # tunable-exempt: calendar
NOTES_KEPT: Final = 40  # tunable-exempt: History notes kept (family.history in balance)
BOARD_MID: Final = 50.0  # tunable-exempt: 45.4's (board confidence - 50) / divisor


def head(state: GameState) -> Person | None:
    family = state.family
    return state.person(family.head_id) if family is not None else None


def children(state: GameState) -> tuple[FamilyMember, ...]:
    """The head's children (45.1), eldest first."""
    family = state.family
    if family is None:
        return ()
    kids = [
        m for m in state.family_members if m.relation == CHILD and family.head_id in m.parent_ids
    ]
    return tuple(sorted(kids, key=lambda m: (state.person(m.person_id).birth_turn, m.person_id)))


def group_ids(state: GameState) -> set[int]:
    """The player's company and the companies it controls (the group, 31.1)."""
    return {c.id for c in group_companies(state, state.player.id)}


def in_group(state: GameState, person_id: int) -> int | None:
    """The group company a family member works at, if any."""
    e = state.employment_of(person_id)
    if e is None or e.company_id not in group_ids(state):
        return None
    return e.company_id


def shown_ceo_fit(state: GameState, person_id: int, balance: Balance) -> float:
    """The CEO-seat score (25.6's weights) from the player's displayed midpoints (18.8):
    never true values."""
    person = state.person(person_id)
    reveal = state.reveal(state.player.id, person_id)
    if reveal is None:
        return 0.0
    skills = {k: sum(revealed_range(person, reveal, k)) / 2 for k in balance.ceo.weights}
    return ceo_score(skills, dict(balance.ceo.weights))


def true_ceo_fit(person: Person, balance: Balance) -> float:
    """The engine's CEO-seat score from true skills (balance targets and the engine only)."""
    return ceo_score({k: person.skills[k] for k in balance.ceo.weights}, dict(balance.ceo.weights))


def readiness_points(state: GameState, member: FamilyMember, balance: Balance) -> float:
    """45.4: displayed fit + years in the group + seats held + the board's confidence."""
    rb = balance.family.ready
    fit = shown_ceo_fit(state, member.person_id, balance)
    if in_group(state, member.person_id) is None or member.company_turn is None:
        return fit
    years = min(rb.years_cap, (state.turn - member.company_turn) / MONTHS_A_YEAR)
    board = average_confidence(state, state.player.id)
    board_pts = (board - BOARD_MID) / rb.board_divisor if board is not None else 0.0
    return fit + rb.per_year * years + rb.per_seat * len(member.seats_held) + board_pts


def readiness(state: GameState, member: FamilyMember, balance: Balance) -> str:
    """A band (45.4): not ready below the first threshold; outside the group, not ready."""
    if in_group(state, member.person_id) is None:
        return READINESS[0]
    points = readiness_points(state, member, balance)
    band = READINESS[0]
    for name, at in zip(READINESS[1:], balance.family.ready.bands, strict=True):
        if points >= at:
            band = name
    return band


def eligible_heirs(state: GameState, balance: Balance, least: str = "not_ready") -> list[int]:
    """Children at least family.heir_min_age, in the group, at least `least` ready, readiest
    first (ties: the eldest)."""
    out = []
    for m in children(state):
        person = state.person(m.person_id)
        if person.age(state.turn) < balance.family.heir_min_age:
            continue
        if in_group(state, m.person_id) is None:
            continue
        if READINESS.index(readiness(state, m, balance)) < READINESS.index(least):
            continue
        out.append(m.person_id)
    out.sort(
        key=lambda pid: (
            -readiness_points(state, member_of(state, pid), balance),
            state.person(pid).birth_turn,
        )
    )
    return out


def member_of(state: GameState, person_id: int) -> FamilyMember:
    m = family_member(state, person_id)
    assert m is not None
    return m


def family_people(state: GameState) -> set[int]:
    """Everyone whose shares count as the family's: members (not ex-partners), the head and
    every former head."""
    family = state.family
    if family is None:
        return set()
    out = {m.person_id for m in state.family_members if m.relation != "ex_partner"}
    out.add(family.head_id)
    out.update(g.person_id for g in family.generations)
    return out


def family_bp(state: GameState, company_id: int | None = None) -> int:
    """The family's share of fully diluted shares (bp): its people and the trust (45.6)."""
    cid = listed_id(state) if company_id is None else company_id
    fd = fd_shares(state, cid)
    if fd <= 0:
        return 0
    people = family_people(state)
    held = sum(
        e.shares
        for e in state.company_cap(cid)
        if (e.holder_kind == "person" and e.person_id in people)
        or (e.holder_kind == "group" and e.name == TRUST_HOLDER)
    )
    return int(Fraction(held * BP_DENOMINATOR, fd))


def check_control(state: GameState, balance: Balance) -> GameState:
    """A loss of family control (45.7): below family.control_bp after having it."""
    family = state.family
    if family is None:
        return state
    has = family_bp(state) >= balance.family.control_bp
    if family.had_control and not has:
        family = replace(family, had_control=False, control_losses=family.control_losses + 1)
        family = note(family, state.turn, "control_lost", "The family lost control of the company")
    elif not family.had_control and has:
        family = replace(family, had_control=True)
    return with_family(state, family)


def note(family: Family, turn: int, kind: str, text: str, keep: int = NOTES_KEPT) -> Family:
    """The family record with one more History note (the last `keep`)."""
    return replace(family, notes=(*family.notes, FamilyNote(turn, kind, text))[-keep:])


def full_name(person: Person) -> str:
    return f"{person.first_name} {person.last_name}"


def roles_match(person: Person, role_key: str, data: GameData) -> bool:
    """45.4: the role matches their interests when the role's interest weights favour one
    of them (any weight above the role's mean weight)."""
    role = data.role(role_key)
    weights = role.interest_weights
    if not weights:
        return True
    mean = sum(weights.values()) / len(weights)
    return any(weights.get(i, 0.0) > mean for i in person.interests)
