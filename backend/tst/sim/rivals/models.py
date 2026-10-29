"""Frozen rival models (docs/formulas.md section 15, ADR-0010).

A rival is an ordinary `CompanyState` (is_player false) with a personality. Its staff are
key people (persons with an employment at the rival) plus workforce pools per function.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type Function = Literal["builder", "seller", "marketer"]
type EffectKind = Literal["feature_push", "quality_push", "brand_push", "cut_costs", "builder_left"]
type ApproachStatus = Literal["pending", "accepted", "declined", "lapsed", "joined"]
type FreeAgentStatus = Literal["available", "placed", "expired"]


@dataclass(frozen=True, slots=True)
class WorkforcePool:
    """A rival's aggregate staff in one function (15.1): headcount, mean skill and morale."""

    company_id: int
    function: Function
    headcount: float
    skill: float
    morale: float


@dataclass(frozen=True, slots=True)
class RivalEffect:
    """Something running on a rival's product for a few months (15.2): a push, a cost cut's
    drag, or the quality lost when a key builder leaves for the player."""

    id: int
    company_id: int
    kind: EffectKind
    start_turn: int
    end_turn: int  # last turn the effect applies
    product_id: int | None = None  # None for a cost cut, which drags every product


@dataclass(frozen=True, slots=True)
class RivalMove:
    """One rival action or startup event, for news, cooldowns and stance (15.3, 15.5)."""

    id: int
    company_id: int
    turn: int
    action: str  # a RIVAL_ACTIONS key, or founded, launched, funded, failed
    product_id: int | None = None
    segment: str | None = None
    detail: str = ""  # rendered words for the news line ("cut SMB prices 10%")


@dataclass(frozen=True, slots=True)
class PoachApproach:
    """A rival's offer to one of the player's people (15.6); answered in phase 1."""

    id: int
    rival_id: int
    person_id: int
    offer_cents: int
    made_turn: int
    status: ApproachStatus = "pending"
    resolved_turn: int | None = None


@dataclass(frozen=True, slots=True)
class FreeAgent:
    """A failed rival's employee looking for work (M6 sub-task 0): they join the player's
    next search for their role until `until_turn`."""

    person_id: int
    role: str
    released_turn: int
    until_turn: int  # leaves the pool in phase 12 of this turn
    status: FreeAgentStatus = "available"


@dataclass(frozen=True, slots=True)
class SegmentShare:
    """A product's share of a segment's served customers at the last month ends, oldest
    first (15.3 needs: share change over the window)."""

    product_id: int
    segment: str
    history: tuple[float, ...] = ()
