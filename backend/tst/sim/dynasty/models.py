"""M37's records (docs/formulas.md 52): pure data, no state imports. A game before January
2040 never holds one: `GameState.dynasty` stays None (52.5 target 1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type SuccessorKind = Literal["heir", "insider", "outside"]
type DeathRole = Literal["head", "member", "adviser"]


@dataclass(frozen=True, slots=True)
class LeaderChange:
    """A rival leader's retirement and successor (52.3), public once it happens."""

    company_id: int
    turn: int
    old_person_id: int | None
    new_person_id: int
    how: SuccessorKind
    old_age: int | None = None
    old_name: str = ""  # the people's names then: a retired leader leaves the live state
    new_name: str = ""
    personality_before: str | None = None
    personality_after: str | None = None


@dataclass(frozen=True, slots=True)
class Death:
    """A founder's or family member's death (52.4), public once it happens."""

    person_id: int
    turn: int
    age: int
    role: DeathRole
    name: str = ""


@dataclass(frozen=True, slots=True)
class Relaunch:
    """A failed rival's brand bought and relaunched by a new entrant (52.3)."""

    company_id: int
    brand_of: int  # the failed company whose brand it carries
    turn: int


@dataclass(frozen=True, slots=True)
class DynastyState:
    """What dynasty years have recorded, oldest first."""

    leader_changes: tuple[LeaderChange, ...] = ()
    deaths: tuple[Death, ...] = ()
    relaunches: tuple[Relaunch, ...] = ()
