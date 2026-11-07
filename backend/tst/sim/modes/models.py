"""M15b records (docs/formulas.md 30): pure data, no state imports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class CompanyScore:
    """One company's score at a turn, with its parts (each part 0-1 except value)."""

    company_id: int
    turn: int
    score: int
    value_cents: int  # market cap, else the displayed value range's midpoint
    growth: float
    profit: float
    leadership: float
    reputation: float
    revenue_cents: int  # trailing 12 months, for the next snapshots' growth


type ModeKind = Literal["campaign", "sandbox", "scenario"]
type RivalsOption = Literal["all", "half", "none"]
type ErasOption = Literal["historical", "seeded"]
type ListKind = Literal["revenue", "places", "innovative"]


@dataclass(frozen=True, slots=True)
class GameMode:
    """How a save plays (30.2-30.3). A save without one is a standard campaign."""

    kind: ModeKind
    start_turn: int = 0
    scenario: str | None = None  # a scenarios.yaml key
    rivals: RivalsOption = "all"
    eras: ErasOption = "historical"
    result: Literal["success", "failure"] | None = None  # a scenario's verdict at its deadline
    result_turn: int | None = None


@dataclass(frozen=True, slots=True)
class Ranking:
    """One place in one January's list (30.4)."""

    turn: int  # the January it was published
    kind: ListKind
    place: int  # 1 = first
    company_id: int
    value: float  # the list's measure: revenue cents, or the 0-1 composite


@dataclass(frozen=True, slots=True)
class QuarterMark:
    """A product's quality and customers when the last quarterly reports were written: the
    next reports' starting values ("41 -> 47"; an M13b follow-up)."""

    product_id: int
    turn: int
    quality: float
    customers: float


type VentureOutcome = Literal["exit"]


@dataclass(frozen=True, slots=True)
class Venture:
    """A company the player ran and sold (M15b addendum 10): History, the score and the Hall
    of Fame show each apart."""

    company_id: int
    name: str
    founded_turn: int
    ended_turn: int
    outcome: VentureOutcome
    buyer_id: int | None = None
    price_cents: int = 0  # the sale price, every share
    proceeds_cents: int = 0  # the founder's share of it
    kept_cents: int = 0  # what the founder kept rather than put into the next company
