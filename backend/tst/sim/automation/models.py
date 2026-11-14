"""Automation records (docs/formulas.md 40, M27a)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# What one line of an owner's month was (40.3, 40.4).
type DecisionKind = Literal[
    "decision",  # the right rule acted
    "mistake",  # the area's stated mistake acted (visible as a misstep)
    "proposal",  # at or above the limit, or a one-off: waiting for the player
    "no_time",  # the owner's energy ran out before this area (40.3)
    "over_budget",  # the owner's month had committed monthly_limit_mult x its limit (40.2)
    "event",  # a routine event answered for the player (40.5)
    "kpi",  # an area KPI's value at the month's start: text = the KPI key (40.4)
]
type OwnerKind = Literal["seat", "ceo", "lead", "subsidiary_ceo"]


@dataclass(frozen=True, slots=True)
class AreaOwner:
    """A person who runs an area of a company (40.1). No row: the player manages it."""

    company_id: int
    area: str  # balance.automation.areas key
    person_id: int
    limit_cents: int  # per decision; at or above it a decision becomes a proposal (40.2)
    priority: int  # the order the owner runs its areas in, lowest first (40.3)
    since_turn: int
    answer_events: bool = True  # "Let them answer routine events" (40.5)
    allow_bold: bool = False  # press: "allow bold claims" (40.6)


@dataclass(frozen=True, slots=True)
class AreaDecision:
    """One logged line of an owner's month (40.3's visible record; 40.4's digest)."""

    company_id: int
    turn: int
    seq: int  # order within the company's month
    area: str
    person_id: int
    kind: DecisionKind
    text: str
    commitment_cents: int = 0  # cash cost over 12 months plus fixed obligations (40.2)
    ref_id: int | None = None  # the proposal or event it concerns
