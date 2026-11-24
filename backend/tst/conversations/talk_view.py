"""What a talk may show (docs/formulas.md 61.3 target 5): the allowlist. The API and every
prompt builder read a talk only through `public`, which copies the counterpart's public facts,
the questions and their displayed facts, the answers and their moves, the promise on offer in
words and, once the talk is done, its visible effects. It never copies `TalkHidden` (the
receptiveness, the founder's or delegate's factor, a person's personality factors), a draw, a
rival's offer amount, or a retention chance.

A reaction to an answer is worded from the answer's moves alone (the published table), never
from the hidden scaling, so a reaction tells nothing a hidden value would."""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.talks.config import MOVES, TalksBalance
from tst.sim.talks.models import Talk

MOVE_WORDS = {
    "bold_claim": "made a bold claim",
    "measured": "gave a measured answer",
    "deflect": "deflected",
    "apologise": "apologised",
    "promise": "made the promise",
    "attack_rival": "took aim at the rival",
    "no_comment": "said no comment",
    "take_responsibility": "took responsibility",
    "listen": "listened",
    "promise_promotion": "promised a promotion",
    "offer_raise": "offered a raise",
    "offer_equity": "offered options",
    "reassign": "offered a new role or area",
    "push_harder": "pushed them harder",
    "praise": "praised their work",
    "warn": "gave a warning",
    "neutral": "no effect",
}
MOVE_LABELS = {
    "bold_claim": "Make a bold claim",
    "measured": "Give a measured answer",
    "deflect": "Deflect",
    "apologise": "Apologise",
    "promise": "Make the promise",
    "attack_rival": "Take aim at the rival",
    "no_comment": "No comment",
    "take_responsibility": "Take responsibility",
    "listen": "Listen",
    "promise_promotion": "Promise a promotion",
    "offer_raise": "Offer a raise",
    "offer_equity": "Offer options",
    "reassign": "Offer a new role or area",
    "push_harder": "Push harder",
    "praise": "Praise their work",
    "warn": "Warn them",
    "neutral": "Say nothing of substance",
}
REACTIONS = {
    "pleased": "That's good to hear.",
    "noted": "Okay.",
    "unconvinced": "I'm not sure that answers it.",
}
PLEASED_FROM = 0.3  # display only: a reaction's words
UNCONVINCED_BELOW = -0.1  # display only


@dataclass(frozen=True, slots=True)
class PublicCounterpart:
    name: str
    role: str
    organisation: str
    person_id: int | None
    beat: str
    stance: str
    morale: int | None


@dataclass(frozen=True, slots=True)
class PublicQuestion:
    n: int
    topic: str
    title: str
    question: str
    facts: tuple[str, ...]
    offer: str
    rival: str


@dataclass(frozen=True, slots=True)
class PublicMove:
    kind: str
    words: str


@dataclass(frozen=True, slots=True)
class PublicAnswer:
    n: int
    claimed: tuple[PublicMove, ...]
    moves: tuple[PublicMove, ...]
    reaction: str
    reaction_words: str


@dataclass(frozen=True, slots=True)
class PublicEffect:
    what: str
    change: float
    words: str


@dataclass(frozen=True, slots=True)
class PublicTalk:
    kind: str
    subject: str
    source: str
    status: str
    opened_turn: int
    counterpart: PublicCounterpart
    questions: tuple[PublicQuestion, ...]
    answers: tuple[PublicAnswer, ...]
    next_question: int | None
    moves: tuple[tuple[str, str], ...]  # the kind's move set: (kind, label)
    offer: str  # the promise on offer, in words ("" for none)
    approached_by: str  # a rival that approached the person ("" for none), never its offer
    delegated_to: int | None
    effects: tuple[PublicEffect, ...]


def reaction_of(strength: float) -> str:
    if strength >= PLEASED_FROM:
        return "pleased"
    return "unconvinced" if strength < UNCONVINCED_BELOW else "noted"


def _effects(talk: Talk) -> tuple[PublicEffect, ...]:
    e = talk.effects
    if e is None or talk.status != "done":
        return ()
    out: list[PublicEffect] = []
    if e.tone:
        out.append(PublicEffect("tone", 0.0, f"the press reads it as a {e.tone} answer"))
    if e.brand_pct:
        out.append(
            PublicEffect(
                "brand",
                e.brand_pct,
                f"brand target {e.brand_pct:+.1f}% for {e.brand_months} months",
            )
        )
    if e.credibility:
        out.append(PublicEffect("credibility", e.credibility, f"credibility {e.credibility:+.1f}"))
    if e.persona is not None:
        out.append(
            PublicEffect("persona", e.persona[1], f"{e.persona[0]} {e.persona[1]:+.1f} (persona)")
        )
    if e.inspection_chance:
        out.append(PublicEffect("regulator", 0.0, "the regulator takes note of the deflection"))
    if e.morale:
        out.append(PublicEffect("morale", e.morale, f"morale {e.morale:+.1f}"))
    if e.loyalty:
        word = "more loyal" if e.loyalty > 0 else "less loyal"
        out.append(PublicEffect("loyalty", e.loyalty, f"{talk.counterpart.name} feels {word}"))
    if e.stress:
        out.append(PublicEffect("stress", e.stress, f"stress {e.stress:+.0f}"))
    if e.retain_chance:
        out.append(PublicEffect("approach", 0.0, "they will think again about the rival's offer"))
    if e.offer_raise:
        out.append(PublicEffect("raise", 0.0, "a raise from the next payroll"))
    if e.equity_bp:
        out.append(PublicEffect("options", 0.0, "an option grant from the pool"))
    if e.reveal:
        out.append(PublicEffect("reveal", 0.0, "you learn their interests and work style"))
    if e.promise is not None:
        out.append(PublicEffect("promise", 0.0, f"you promised {e.promise.words}"))
    return tuple(out)


def public(talk: Talk, tb: TalksBalance) -> PublicTalk:
    from tst.sim.talks.engine import strength_public
    from tst.sim.talks.opening import subject_title

    qs = {q.n: q for q in talk.questions}
    nxt = talk.next_question
    c = talk.counterpart
    rival = next((q.rival for q in talk.questions if q.topic == "approach"), "")
    return PublicTalk(
        kind=talk.kind,
        subject=subject_title(talk),
        source=talk.subject.source,
        status=talk.status,
        opened_turn=talk.opened_turn,
        counterpart=PublicCounterpart(
            c.name, c.role, c.organisation, c.person_id, c.beat, c.stance, c.morale
        ),
        questions=tuple(
            PublicQuestion(q.n, q.topic, q.title, q.question, q.facts, q.offer, q.rival)
            for q in talk.questions
        ),
        answers=tuple(
            PublicAnswer(
                a.n,
                tuple(PublicMove(m.kind, MOVE_WORDS.get(m.kind, "no effect")) for m in a.claimed),
                tuple(PublicMove(m.kind, MOVE_WORDS.get(m.kind, "no effect")) for m in a.moves),
                reaction_of(strength_public(talk, qs[a.n], a.moves, tb)),
                REACTIONS[reaction_of(strength_public(talk, qs[a.n], a.moves, tb))],
            )
            for a in talk.answers
        ),
        next_question=nxt.n if nxt is not None and talk.status == "open" else None,
        moves=tuple((k, MOVE_LABELS[k]) for k in MOVES[talk.kind]),
        offer=talk.offer.words if talk.offer is not None else "",
        approached_by=rival,
        delegated_to=talk.delegate_id,
        effects=_effects(talk),
    )
