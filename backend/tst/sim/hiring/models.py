"""Frozen hiring models: searches, candidates, offers, per-person state, id counters.

GameState holds live records only (M1b sweep rule 1): open searches, open candidates,
pending offers, and staff. A record whose status changes during a turn or action stays in
the resulting state so persistence can store the new status; the next load drops it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

type Channel = Literal["network", "job_post", "recruiter"]
type SearchStatus = Literal["open", "closed"]
# "withdrawn" is unused in M1: M2 uses it when a candidate or a delegate pulls out.
type CandidateStatus = Literal["open", "hired", "declined", "expired", "withdrawn"]
type OfferStatus = Literal["pending", "accepted", "declined", "withdrawn"]


@dataclass(frozen=True, slots=True)
class Search:
    id: int
    company_id: int
    role: str
    channel: Channel
    actor_id: int  # who opened it; their judgment scouts the batch
    opened_turn: int
    status: SearchStatus = "open"
    closed_turn: int | None = None


@dataclass(frozen=True, slots=True)
class Candidate:
    """A generated person available to one company (the person lives in GameState.people)."""

    person_id: int
    company_id: int
    search_id: int
    created_turn: int  # turn whose phase 12 generated the batch
    expires_turn: int  # leaves in phase 12 of this turn unless hired first
    status: CandidateStatus = "open"
    resolved_turn: int | None = None


@dataclass(frozen=True, slots=True)
class Offer:
    id: int
    company_id: int
    candidate_id: int  # person id
    actor_id: int
    salary_cents: int
    equity_bp: int
    made_turn: int
    status: OfferStatus = "pending"
    resolved_turn: int | None = None


@dataclass(frozen=True, slots=True)
class PersonState:
    """Mutable-per-turn values for one person. None means not tracked for this person."""

    person_id: int
    energy: int | None = None  # founder only (formulas.md section 6)
    stress: float | None = None  # M3+
    morale: float | None = None  # employees, not the founder (formulas.md section 9)


@dataclass(frozen=True, slots=True)
class NextIds:
    """Id counters persisted in save_meta (M1b sweep rule 2); ids are never reused."""

    person: int = 1
    search: int = 1
    offer: int = 1
    employment: int = 1

    def take(self, kind: Literal["person", "search", "offer", "employment"]) -> tuple[int, NextIds]:
        value: int = getattr(self, kind)
        return value, replace(self, **{kind: value + 1})

    def take_many(self, kind: Literal["person"], count: int) -> tuple[int, NextIds]:
        first: int = getattr(self, kind)
        return first, replace(self, **{kind: first + count})
