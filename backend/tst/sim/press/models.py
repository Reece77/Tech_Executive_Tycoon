"""M14b state (docs/formulas.md 29): press moments, public promises, credibility, rival
CEOs' statements and feuds. Everything here is public (29.6) except where marked."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MomentStatus = Literal["pending", "queued", "skipped", "answered"]
PromiseStatus = Literal["open", "kept", "broken"]
type Fact = tuple[str, int | str]
type Cause = tuple[int, float, str]  # (turn, change, cause in words)


@dataclass(frozen=True, slots=True)
class PressMoment:
    """One press moment (29.1). Queued by the engine (`queue_moment`) as "pending"; phase 12
    keeps at most press.max_per_quarter a quarter and one a month, highest stakes first,
    and queues its event for `event_turn`; the event's answer sets `tone`."""

    id: int
    company_id: int
    trigger: str
    turn: int  # the month it was raised
    status: MomentStatus = "pending"
    event_turn: int | None = None  # the month its event is shown
    product_id: int | None = None
    rival_id: int | None = None  # the rival company it names, if any
    facts: tuple[Fact, ...] = ()  # displayed facts only: words for the template and the LLM
    tone: str | None = None
    answered_turn: int | None = None
    # A bold claim (29.1): the product's displayed share when it was made, and whether it has
    # backfired. Hidden only in that the API never shows a backfire before it happens.
    share_bp: int | None = None
    backfired: bool = False


@dataclass(frozen=True, slots=True)
class Promise:
    """A public promise (29.2), judged on displayed values only."""

    id: int
    company_id: int
    kind: str  # config.PROMISE_KINDS
    made_turn: int
    deadline_turn: int
    moment_id: int | None = None
    product_id: int | None = None  # ship, beat, no price rise
    rival_product_id: int | None = None  # beat
    domain: str | None = None  # research
    level: int | None = None  # research: the displayed lead to reach
    baseline: int = 0  # the displayed value when made (quality or lead)
    prices: tuple[tuple[str, int], ...] = ()  # no price rise: the displayed prices when made
    ambition: float = 0.0
    audience: float = 1.0  # a when made
    status: PromiseStatus = "open"
    resolved_turn: int | None = None
    reminder_turn: int | None = None  # a broken promise's "you said ..." month

    @property
    def open(self) -> bool:
        return self.status == "open"


@dataclass(frozen=True, slots=True)
class Credibility:
    """A company's public credibility, 0-100 (29.3), with its last changes and causes."""

    company_id: int
    value: float
    history: tuple[Cause, ...] = ()
    # The month's firings, for a layoffs moment (29.1): kept here because ended employments
    # leave the live state between actions.
    fired_turn: int | None = None
    fired: int = 0
    staff_start: int = 0


@dataclass(frozen=True, slots=True)
class Feud:
    """The player's founder against one rival's CEO, 0-100 (29.4)."""

    company_id: int  # the player's company
    rival_id: int
    score: float = 0.0
    causes: tuple[Cause, ...] = ()
    rivalry_turn: int | None = None  # when it last reached rivalry

    def rivalry(self, at: float) -> bool:
        return self.score >= at


@dataclass(frozen=True, slots=True)
class Statement:
    """A rival CEO's public statement (29.4): at their own launch or price cut, or in answer
    to a bold claim that named them. A jab is aimed at the player and opens a moment."""

    id: int
    rival_id: int
    person_id: int
    turn: int
    kind: Literal["statement", "jab", "answer"]
    text: str
    product_id: int | None = None


@dataclass(frozen=True, slots=True)
class Departure:
    """Someone who resigned or was poached lately (29.5): Replace's source once their
    employment has ended and left the live state. Kept recruit.replace_window months."""

    person_id: int
    company_id: int
    role: str
    level: str
    unit_id: int | None
    reason: str  # resigned | poached
    turn: int
