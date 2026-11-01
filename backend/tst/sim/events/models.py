"""Frozen event models (docs/formulas.md 16; ADR-0005, ADR-0012).

Phase 12 of turn T queues next month's events as `GameEvent`s with status "pending" and
returns an `EventRequest` for each. After the turn commits, the event service writes the
words and the validated choices (status "open"); the player answers during month T + 1, or
Continue answers minor and major ones with their first choice. Values in `Effect` are in
the effect's own units (16.3): morale, relationship, brand, quality, energy and confidence
points; cents for cash; percent for customers and salary; skill points for growth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tst.sim.events.data import Severity

type EventStatus = Literal["pending", "open", "answered", "auto"]
type StorylineStatus = Literal["active", "ended"]
type Tone = Literal["grounded", "light"]


@dataclass(frozen=True, slots=True)
class Effect:
    """One validated effect. `target` is "person:<id>", "pair:<a>-<b>", "unit:<id>",
    "company:<id>", "product:<id>", "founder:<id>", "board" or "" (follow_up)."""

    type: str
    target: str
    value: float = 0.0


@dataclass(frozen=True, slots=True)
class EventChoice:
    key: str
    label: str
    effects: tuple[Effect, ...] = ()


@dataclass(frozen=True, slots=True)
class GameEvent:
    id: int
    company_id: int
    turn: int  # the month it is shown in (queued in phase 12 of turn - 1)
    template_id: str
    category: str
    severity: Severity
    trigger: str
    strength: float
    person_ids: tuple[int, ...] = ()  # the trigger's people (a pair: two)
    unit_id: int | None = None
    product_id: int | None = None
    segment: str | None = None
    rival_id: int | None = None
    months: int | None = None  # runway months, for runway_short
    cash_base_cents: int = 0  # max(cash, 3 x monthly revenue) when queued (16.3)
    tone: Tone = "grounded"
    storyline_id: int | None = None
    loan_id: int | None = None  # M10: a lender event's loan (20.3)
    status: EventStatus = "pending"
    title: str = ""
    body: str = ""
    choices: tuple[EventChoice, ...] = ()
    chosen: str | None = None
    resolved_turn: int | None = None
    source: str = ""  # who wrote the words: claude, template, mock or replay

    @property
    def is_open(self) -> bool:
        return self.status in ("pending", "open")

    def choice(self, key: str) -> EventChoice | None:
        return next((c for c in self.choices if c.key == key), None)


@dataclass(frozen=True, slots=True)
class Storyline:
    """A multi-month thread of template steps (16.6)."""

    id: int
    company_id: int
    key: str  # the template storyline key
    title: str
    step: int  # the last step queued
    started_turn: int
    summary: str
    person_ids: tuple[int, ...] = ()
    product_id: int | None = None
    rival_id: int | None = None
    unit_id: int | None = None
    segment: str | None = None
    next_turn: int | None = None  # the month the next step is shown in
    next_template: str | None = None
    status: StorylineStatus = "active"
    ended_turn: int | None = None


@dataclass(frozen=True, slots=True)
class QueuedEvent:
    """A follow-up of a critical event, queued when the player answers it (16.3)."""

    id: int
    company_id: int
    template_id: str
    due_turn: int  # the month it is shown in
    source_event_id: int | None  # None: queued by the engine (a lender event, M10)
    person_ids: tuple[int, ...] = ()
    product_id: int | None = None
    unit_id: int | None = None
    rival_id: int | None = None
    segment: str | None = None
    done: bool = False
    loan_id: int | None = None  # M10: a lender event queued by the engine (20.3)


@dataclass(frozen=True, slots=True)
class EventRequest:
    """What phase 12 asks the event service to write (ADR-0012). The service reads the
    stored event and the state for everything else; `targets` is the eligible list."""

    event_id: int
    company_id: int
    turn: int
    template_id: str
    severity: Severity
    tone: Tone
    targets: tuple[str, ...]
    storyline_id: int | None = None


@dataclass(frozen=True, slots=True)
class TextRequest:
    """Read-only LLM text (16.8): monthly headlines, quarterly board minutes, an
    exit-interview line. `ref_id` is the person for an exit line."""

    kind: Literal["headlines", "minutes", "exit_line"]
    company_id: int
    turn: int
    ref_id: int | None = None
