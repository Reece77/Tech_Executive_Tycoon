"""Frozen hiring models: searches, candidates, offers, per-person state, id counters.

GameState holds live records only (M1b sweep rule 1): open searches, open candidates,
pending offers, and staff. A record whose status changes during a turn or action stays in
the resulting state so persistence can store the new status; the next load drops it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

type Channel = Literal["network", "job_post", "recruiter", "poach"]  # poach: M5 (15.6)
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
    plan_id: int | None = None  # the hiring plan it serves (opened by its delegate, M2a)
    rival_id: int | None = None  # a "Poach from a rival" search: the rival (M5, 15.6)
    level: str | None = None  # "exec": every candidate at exec level (M8, 18.3); None: the mix
    # M9 (19.3): the city candidates live in (relocators move there), ANYWHERE for a remote
    # unit's search, None for searches opened before M9 (generated as v1 did).
    city: str | None = None


@dataclass(frozen=True, slots=True)
class Candidate:
    """A generated person available to one company (the person lives in GameState.people)."""

    person_id: int
    company_id: int
    search_id: int
    channel: Channel  # kept here because one-batch searches close (recruiter fee on hire)
    created_turn: int  # turn whose phase 12 generated the batch
    expires_turn: int  # leaves in phase 12 of this turn unless hired first
    status: CandidateStatus = "open"
    resolved_turn: int | None = None
    interviewed_turn: int | None = None  # first interview by this company (ADR-0016)
    relocate_to: str | None = None  # M9 (19.3): the search's city, for one who lives elsewhere


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
    plan_id: int | None = None  # the hiring plan a delegate made it under
    unit_id: int | None = None  # where the hire joins; None = the company root


@dataclass(frozen=True, slots=True)
class PersonState:
    """Mutable-per-turn values for one person. None means not tracked for this person."""

    person_id: int
    energy: int | None = None  # founder and delegates (formulas.md sections 6, 13.10)
    stress: float | None = None  # M3+
    morale: float | None = None  # employees, not the founder (formulas.md section 9)


RIVAL_IDS_FROM = 1_000_001  # tunable-exempt: first id of rivals' own people and employments


@dataclass(frozen=True, slots=True)
class NextIds:
    """Id counters persisted in save_meta (M1b sweep rule 2); ids are never reused."""

    person: int = 1
    search: int = 1
    offer: int = 1
    employment: int = 1
    unit: int = 1
    plan: int = 1
    product: int = 1  # M3
    cap_entry: int = 1  # M4
    grant: int = 1
    safe: int = 1
    round: int = 1
    term_sheet: int = 1
    seat: int = 1
    rival_effect: int = 1  # M5
    rival_move: int = 1
    approach: int = 1
    # Rivals' own people and employments count from here, apart from the player's (M5): the
    # player's ids stay as before rivals existed.
    rival_person: int = RIVAL_IDS_FROM
    rival_employment: int = RIVAL_IDS_FROM
    # M6: loaded as max(id) + 1 of their tables, not kept in save_meta (an old save's
    # migration 0013 reads save_meta through the current model).
    event: int = 1
    storyline: int = 1
    queued: int = 1
    loan: int = 1  # M10: loaded as max(id) + 1 of the loan table, like the M6 counters
    office: int = 1  # M9: loaded as max(id) + 1 of the office table, like M6's counters
    modifier: int = 1  # M10b: loaded as max(id) + 1 of the event_modifier table

    def take(
        self,
        kind: Literal[
            "person",
            "search",
            "offer",
            "employment",
            "unit",
            "plan",
            "product",
            "cap_entry",
            "grant",
            "safe",
            "round",
            "term_sheet",
            "seat",
            "rival_effect",
            "rival_move",
            "approach",
            "rival_person",
            "rival_employment",
            "event",
            "storyline",
            "queued",
            "loan",
            "office",
            "modifier",
        ],
    ) -> tuple[int, NextIds]:
        value: int = getattr(self, kind)
        return value, replace(self, **{kind: value + 1})

    def take_many(self, kind: Literal["person"], count: int) -> tuple[int, NextIds]:
        first: int = getattr(self, kind)
        return first, replace(self, **{kind: first + count})
