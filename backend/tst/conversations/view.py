"""What a negotiation may show (docs/formulas.md 58.6): the allowlist. The API and every prompt
builder read a negotiation only through `public`, which copies the opening offer, the
counterpart's public facts and stated reasons, the ranges as revealed, the rounds and their
moves, and never the hidden zone, aspiration, patience, priorities, openness or draws."""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.money import format_money
from tst.sim.negotiation import engine
from tst.sim.negotiation.config import NegotiationBalance
from tst.sim.negotiation.models import BP, Move, Negotiation, TermSpec

# 16.7's relationship labels, lowest first: (from, label)
LABELS = ((-1000, "hostile"), (-49, "strained"), (-19, "neutral"), (20, "good"), (60, "close"))
REASON_WORDS = {
    "far_apart": "We are still far apart.",
    "moving": "We are moving, but not there yet.",
    "close": "We are close.",
    "final_offer": "This is our final offer.",
    "accepted": "We have a deal.",
    "walked_threat": "They walked away: you threatened to walk with an offer they could not take.",
    "walked_patience": "They ran out of patience and walked away.",
}
MOVE_WORDS = {
    "concede": "conceded",
    "anchor": "anchored",
    "justify": "justified",
    "appeal": "appealed to the relationship",
    "threaten_walk": "threatened to walk",
    "package": "proposed a package",
    "close": "asked to close",
    "neutral": "no effect",
}


def relationship_label(value: int) -> str:
    label = LABELS[0][1]
    for start, word in LABELS:
        if value >= start:
            label = word
    return label


def show_value(term: TermSpec, value: int) -> str:
    """A term's value in words: money, or a quote's share as its price."""
    if term.unit == "cents":
        return format_money(value)
    price = term.base * value / BP  # money-exact: display only
    pct = f"{value / 100:.1f}% of the quote"
    if term.base_is_cents:
        return f"{format_money(round(price))} {term.base_unit} ({pct})"
    return f"{price:,.2f} {term.base_unit} ({pct})"


@dataclass(frozen=True, slots=True)
class PublicTerm:
    key: str
    label: str
    unit: str
    wants: str
    base_shown: str  # the quote, for a bp term ("" for a sum)


@dataclass(frozen=True, slots=True)
class PublicMove:
    kind: str
    term: int | None
    other: int | None
    fact: int | None
    words: str


@dataclass(frozen=True, slots=True)
class PublicRound:
    n: int
    offer: tuple[int, ...]
    offer_shown: tuple[str, ...]
    claimed: tuple[PublicMove, ...]
    moves: tuple[PublicMove, ...]
    counter_before: tuple[int, ...]
    counter: tuple[int, ...]
    counter_shown: tuple[str, ...]
    outcome: str
    reason: str
    reason_words: str
    mood: str
    relationship_change: int


@dataclass(frozen=True, slots=True)
class PublicRange:
    lo: int
    hi: int
    shown: str


@dataclass(frozen=True, slots=True)
class PublicNegotiation:
    kind: str
    subject: str
    status: str
    terms: tuple[PublicTerm, ...]
    counterpart_name: str
    counterpart_role: str
    counterpart_organisation: str
    counterpart_style: str
    relationship: str
    facts: tuple[str, ...]
    used_facts: tuple[int, ...]
    persona: tuple[str, ...]
    opening: tuple[int, ...]
    opening_shown: tuple[str, ...]
    counter: tuple[int, ...]
    counter_shown: tuple[str, ...]
    offer: tuple[int, ...] | None
    offer_shown: tuple[str, ...]
    ranges: tuple[PublicRange, ...]
    rounds: tuple[PublicRound, ...]
    mood: str
    final: tuple[int, ...] | None
    final_shown: tuple[str, ...]


def _shown(neg: Negotiation, values: tuple[int, ...] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(show_value(t, v) for t, v in zip(neg.terms, values, strict=True))


def _move(neg: Negotiation, m: Move) -> PublicMove:
    words = MOVE_WORDS[m.kind]
    if m.kind == "justify" and m.fact is not None and 0 <= m.fact < len(neg.facts):
        words = f"justified: {neg.facts[m.fact]}"
    return PublicMove(m.kind, m.term, m.other, m.fact, words)


def public(neg: Negotiation, b: NegotiationBalance) -> PublicNegotiation:
    ranges = engine.revealed(neg, b)
    last = neg.rounds[-1] if neg.rounds else None
    return PublicNegotiation(
        kind=neg.kind,
        subject=neg.subject,
        status=neg.status,
        terms=tuple(
            PublicTerm(
                t.key,
                t.label,
                t.unit,
                t.wants,
                show_value(t, BP) if t.unit == "bp" else "",
            )
            for t in neg.terms
        ),
        counterpart_name=neg.counterpart.name,
        counterpart_role=neg.counterpart.role,
        counterpart_organisation=neg.counterpart.organisation,
        counterpart_style=neg.counterpart.style,
        relationship=relationship_label(neg.relationship),
        facts=neg.facts,
        used_facts=neg.used_facts,
        persona=neg.persona,
        opening=neg.opening,
        opening_shown=_shown(neg, neg.opening),
        counter=neg.counter,
        counter_shown=_shown(neg, neg.counter),
        offer=neg.offer,
        offer_shown=_shown(neg, neg.offer),
        ranges=tuple(
            PublicRange(lo, hi, f"{show_value(t, lo)} to {show_value(t, hi)}")
            for t, (lo, hi) in zip(neg.terms, ranges, strict=True)
        ),
        rounds=tuple(
            PublicRound(
                n=r.n,
                offer=r.offer,
                offer_shown=_shown(neg, r.offer),
                claimed=tuple(_move(neg, m) for m in r.claimed),
                moves=tuple(_move(neg, m) for m in r.moves),
                counter_before=r.counter_before,
                counter=r.counter,
                counter_shown=_shown(neg, r.counter),
                outcome=r.outcome,
                reason=r.reason,
                reason_words=REASON_WORDS[r.reason],
                mood=r.mood,
                relationship_change=r.relationship_change,
            )
            for r in neg.rounds
        ),
        mood=last.mood if last is not None else "open",
        final=neg.final,
        final_shown=_shown(neg, neg.final),
    )
