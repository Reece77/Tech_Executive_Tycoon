"""Negotiation records (docs/formulas.md 58; ADR-0023). A negotiation is one deal's talks: the
deal's public reference (its terms, the counterpart's public facts), the counterpart's hidden
zone and patience (`Hidden`), and the rounds played. Every term's value is an int in its unit:
cents, or basis points of today's quoted price (`bp`, 10,000 = the quote).

`Hidden` and `Negotiation.patience_left` and `level` are never shown and never reach a prompt
(58.6): the API and the prompt builders read only `public` fields (tst.conversations.prompts and
tst.api.negotiation_views list exactly what they read)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from tst.sim.negotiation.config import DealKind, MoveKind

type Unit = Literal["cents", "bp"]
type Wants = Literal["lower", "higher"]  # which way the player wants a term to go
type Status = Literal["open", "agreed", "walked", "skipped"]
type RoundOutcome = Literal["countered", "final", "agreed", "walked"]
# The counterpart's stated reason (58.3: its reply is worded from this, never from numbers).
type Reason = Literal[
    "far_apart",
    "moving",
    "close",
    "final_offer",
    "accepted",
    "walked_threat",
    "walked_patience",
]
type Mood = Literal["open", "firm", "final"]  # how close it is to walking (shown)

BP: Final = 10_000  # tunable-exempt: basis points in a whole (a bp term's median)


@dataclass(frozen=True, slots=True)
class TermSpec:
    """One negotiable term. `base` is what a `bp` term is a share of (the quote, in the
    quote's own unit, for display); 0 for a `cents` term."""

    key: str
    label: str
    unit: Unit
    wants: Wants
    base: float = 0.0
    base_unit: str = ""  # the quote's unit, e.g. "a MWh"
    base_is_cents: bool = False  # the quote is money (cents), else a commodity's price unit


@dataclass(frozen=True, slots=True)
class Counterpart:
    """The person across the table: public facts only (58.2)."""

    name: str
    role: str
    organisation: str
    key: str  # stable: relationship and cool-off are kept per counterpart and deal kind
    person_id: int | None = None
    company_id: int | None = None
    style: str = ""  # a public word for their manner (a rival's personality), or ""


@dataclass(frozen=True, slots=True)
class DealRef:
    """What the engine's existing pricing says about a deal (built by tst.sim.negotiation.deals).
    `medians` are today's terms (the skip outcome, 58.4); `zones` overrides the drawn zone with
    (aspiration, reservation) per term where the deal already has them (an acquisition, 28.3).
    Both are HIDDEN: only `public` facts are shown."""

    kind: DealKind
    key: tuple[int, ...]  # the deal's stream key after the kind index (ADR-0013)
    subject: str
    terms: tuple[TermSpec, ...]
    medians: tuple[int, ...]
    counterpart: Counterpart
    facts: tuple[str, ...]  # public facts the player may cite (a `justify` names one)
    zones: tuple[tuple[int, int], ...] | None = None


@dataclass(frozen=True, slots=True)
class Hidden:
    """The counterpart's hidden values (58.2). Never shown, never in a prompt."""

    aspiration: tuple[int, ...]
    reservation: tuple[int, ...]
    medians: tuple[int, ...]
    patience: int
    priorities: tuple[float, ...]
    openness: float
    offsets: tuple[float, ...]
    skill: float  # the negotiator's factor from true skills (58.3)
    # M57r-B: each round's concession factor's draw, in [-1, 1) (empty in talks opened before)
    jitter: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class Move:
    """One scored move. `term` is the term a concession or package gives on, `other` the term
    a package asks for, `fact` the displayed fact a justification cites (indexes)."""

    kind: MoveKind
    term: int | None = None
    other: int | None = None
    fact: int | None = None


@dataclass(frozen=True, slots=True)
class Round:
    n: int
    offer: tuple[int, ...]
    claimed: tuple[Move, ...]  # the moves as scored (classifier or buttons)
    moves: tuple[Move, ...]  # after the engine's checks (an invalid move is neutral)
    counter_before: tuple[int, ...]
    counter: tuple[int, ...]
    outcome: RoundOutcome
    reason: Reason
    mood: Mood
    relationship_change: int


@dataclass(frozen=True, slots=True)
class Negotiation:
    kind: DealKind
    subject: str
    terms: tuple[TermSpec, ...]
    counterpart: Counterpart
    facts: tuple[str, ...]
    persona: tuple[str, ...]  # the negotiator's public persona traits that count (32.4)
    hidden: Hidden
    level: float  # HIDDEN: the counterpart's demand, 1 = its aspiration, 0 = its reservation
    patience_left: int  # HIDDEN
    counter: tuple[int, ...]  # its offer as shown
    opening: tuple[int, ...]  # its first offer as shown
    offer: tuple[int, ...] | None = None  # the player's last offer
    rounds: tuple[Round, ...] = ()
    status: Status = "open"
    final: tuple[int, ...] | None = None  # the agreed (or skipped) terms
    relationship_start: int = 0
    relationship: int = 0
    used_facts: tuple[int, ...] = ()
