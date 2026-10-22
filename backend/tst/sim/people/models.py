"""Frozen people models (ADR-0002, ADR-0007). Return new objects; never mutate.

True values live here and are used by the sim. What an observer company knows is a
separate `RevealState` per (observer, person); the API only ever sees ranges built from it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal, Self

from tst.sim.calendar import age_at
from tst.sim.data_models import GameData, Role
from tst.sim.people.formulas import current_ability as _ca
from tst.sim.scale import clamp_attr

PA_KEY = "potential_ability"  # reveal record key for potential ability
FOUNDER_ROLE = "founder"  # employment role of the founder (not a hireable role)

type EmploymentStatus = Literal["active", "notice", "ended"]
type EndReason = Literal["resigned", "fired", "retired"]


@dataclass(frozen=True, slots=True)
class AttrSet:
    """An ordered, immutable set of named 1-20 attributes.

    Order follows the data file (skills.yaml, personality.yaml), which fixes the order of
    random draws (ADR-0013). Every value is clamped on construction.
    """

    items: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple((k, clamp_attr(v)) for k, v in self.items))

    @classmethod
    def build(cls, keys: Iterable[str], values: Mapping[str, float]) -> Self:
        return cls(tuple((k, values[k]) for k in keys))

    def __getitem__(self, key: str) -> float:
        for k, v in self.items:
            if k == key:
                return v
        raise KeyError(key)

    def keys(self) -> tuple[str, ...]:
        return tuple(k for k, _ in self.items)

    def as_dict(self) -> dict[str, float]:
        return dict(self.items)

    def updated(self, changes: Mapping[str, float]) -> Self:
        """A copy with some values replaced (clamped)."""
        return type(self)(tuple((k, changes.get(k, v)) for k, v in self.items))


@dataclass(frozen=True, slots=True)
class Skills(AttrSet):
    pass


@dataclass(frozen=True, slots=True)
class Personality(AttrSet):
    pass


@dataclass(frozen=True, slots=True)
class HiddenTraits(AttrSet):
    pass


@dataclass(frozen=True, slots=True)
class Person:
    id: int
    first_name: str
    last_name: str
    region: str
    birth_turn: int
    role: str | None  # role the person was generated for; None = founder (best-fit role)
    level: str | None
    skills: Skills
    personality: Personality
    hidden: HiddenTraits
    potential_ability: float  # hidden, 10-200, never changes
    interests: tuple[str, ...]
    work_style: str
    tags: tuple[str, ...]  # true behavior tags (hidden until revealed per observer)
    salary_expectation_cents: int | None
    is_founder: bool = False

    def age(self, turn: int) -> int:
        return age_at(turn, self.birth_turn)


@dataclass(frozen=True, slots=True)
class RevealRecord:
    """What one observer knows about one attribute: half-width and centre offset."""

    hw: float
    offset: float
    last_updated_turn: int


@dataclass(frozen=True, slots=True)
class RevealState:
    """Everything one observer company knows about one person (ADR-0007)."""

    observer_company_id: int
    person_id: int
    attributes: tuple[tuple[str, RevealRecord], ...]  # skills, personality, then PA_KEY
    profile_revealed_turn: int | None  # interests and work style shown from this turn
    revealed_tags: tuple[tuple[str, int], ...]  # (tag, revealed_turn)

    def record(self, attribute: str) -> RevealRecord:
        for key, rec in self.attributes:
            if key == attribute:
                return rec
        raise KeyError(attribute)


@dataclass(frozen=True, slots=True)
class Employment:
    id: int
    person_id: int
    company_id: int
    role: str
    level: str
    salary_cents: int
    equity_bp: int
    start_turn: int
    end_turn: int | None
    status: EmploymentStatus
    end_reason: EndReason | None = None

    @property
    def counts_as_staff(self) -> bool:
        """Active and notice employments are on the books (headcount, growth)."""
        return self.status != "ended"


# --- Current ability ------------------------------------------------------------------------


def role_ability(skills: Skills, role: Role) -> float:
    return _ca(skills.as_dict(), role.primary, role.secondary)


def best_fit_role(skills: Skills, data: GameData) -> tuple[Role, float]:
    """The role giving the highest CA; ties go to the role listed first (formulas.md 1)."""
    best = data.roles[0]
    best_ca = role_ability(skills, best)
    for role in data.roles[1:]:
        ca = role_ability(skills, role)
        if ca > best_ca:
            best, best_ca = role, ca
    return best, best_ca


def growth_role(person: Person, data: GameData) -> Role:
    """The role whose skills grow: the person's own role, or the founder's best fit."""
    if person.role is None:
        return best_fit_role(person.skills, data)[0]
    return data.role(person.role)


def current_ability(person: Person, data: GameData) -> float:
    """CA for a person: their role's CA, or the founder's best-fit CA (formulas.md 1)."""
    return role_ability(person.skills, growth_role(person, data))
