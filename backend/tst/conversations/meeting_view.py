"""What a meeting may show (docs/formulas.md 59.5): the allowlist. The API and every prompt
builder read a meeting only through `public`, which copies the agenda, the questions and their
displayed facts, the answers and their moves, the speakers' public facts and confidence, the
credibility and, once the meeting is done, its visible effects. It never copies
`MeetingHidden` (the speakers' priorities, receptiveness and the founder's factor) or a draw.

A speaker's reaction to an answer is worded from the answer's moves alone (the fixed effects
table), never from the hidden scaling, so a reaction tells nothing a priority would."""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.meetings.agenda import money_words
from tst.sim.meetings.config import MOVES, MeetingsBalance
from tst.sim.meetings.engine import raw_strength_public
from tst.sim.meetings.models import Meeting, Move

MOVE_WORDS = {
    "commit": "committed to the plan figure",
    "explain": "explained",
    "defer": "deferred",
    "concede": "conceded the point",
    "push_back": "pushed back",
    "reaffirm": "reaffirmed guidance",
    "raise": "raised guidance",
    "lower": "lowered guidance",
    "deflect": "deflected",
    "promise": "promised the figure",
    "neutral": "no effect",
}
MOVE_LABELS = {
    "commit": "Commit to the figure",
    "explain": "Explain with a fact",
    "defer": "Defer",
    "concede": "Concede",
    "push_back": "Push back",
    "reaffirm": "Reaffirm guidance",
    "raise": "Raise guidance",
    "lower": "Lower guidance",
    "deflect": "Deflect",
    "promise": "Promise the figure",
    "neutral": "Say nothing of substance",
}
REACTIONS = {
    "pleased": "That answers it.",
    "noted": "Noted.",
    "unconvinced": "I'm not convinced.",
}
PLEASED_FROM = 0.3  # tunable-exempt: a reaction's words, display only
UNCONVINCED_BELOW = -0.1  # tunable-exempt: display only


@dataclass(frozen=True, slots=True)
class PublicSpeaker:
    key: str
    kind: str
    name: str
    role: str
    organisation: str
    focus: str
    confidence: float | None
    rating: str
    target_cents: int


@dataclass(frozen=True, slots=True)
class PublicItem:
    n: int
    speaker: int
    topic: str
    title: str
    question: str
    facts: tuple[str, ...]
    problem: bool
    figure: str  # the plan figure's words ("" without one)
    guidance: bool


@dataclass(frozen=True, slots=True)
class PublicMove:
    kind: str
    fact: int | None
    words: str


@dataclass(frozen=True, slots=True)
class PublicAnswer:
    n: int
    claimed: tuple[PublicMove, ...]
    moves: tuple[PublicMove, ...]
    reaction: str  # pleased, noted or unconvinced
    reaction_words: str
    commitment: str  # what was committed to ("" for none)


@dataclass(frozen=True, slots=True)
class PublicEffect:
    """A visible effect once the meeting is done: a director's confidence change, an analyst's
    target change, or the market's and credibility's."""

    who: str
    what: str
    change: float
    words: str


@dataclass(frozen=True, slots=True)
class PublicMeeting:
    kind: str
    subject: str
    status: str
    opened_turn: int
    speakers: tuple[PublicSpeaker, ...]
    items: tuple[PublicItem, ...]
    answers: tuple[PublicAnswer, ...]
    next_item: int | None
    moves: tuple[tuple[str, str], ...]  # the kind's move set: (kind, label)
    credibility: float
    persona: tuple[str, ...]
    plan_subject: str
    plan_facts: tuple[str, ...]
    effects: tuple[PublicEffect, ...]
    votes: tuple[tuple[str, bool], ...]  # (director's name, backs the plan)
    commitments: tuple[str, ...]


def _move(meeting: Meeting, item_facts: tuple[str, ...], m: Move) -> PublicMove:
    words = MOVE_WORDS.get(m.kind, "no effect")
    if m.kind == "explain" and m.fact is not None and 0 <= m.fact < len(item_facts):
        words = f"explained: {item_facts[m.fact]}"
    return PublicMove(m.kind, m.fact, words)


def reaction_of(strength: float) -> str:
    if strength >= PLEASED_FROM:
        return "pleased"
    return "unconvinced" if strength < UNCONVINCED_BELOW else "noted"


def _effects(meeting: Meeting) -> tuple[tuple[PublicEffect, ...], tuple[tuple[str, bool], ...]]:
    e = meeting.effects
    if e is None or meeting.status != "done":
        return (), ()
    by_seat = {s.seat_id: s for s in meeting.speakers if s.seat_id is not None}
    by_analyst = {s.analyst_index: s for s in meeting.speakers if s.analyst_index is not None}
    out: list[PublicEffect] = []
    for seat_id, d in e.confidence:
        sp = by_seat[seat_id]
        out.append(PublicEffect(sp.name, "confidence", d, f"{sp.name}: confidence {d:+.1f}"))
    for i, t in e.targets:
        sp = by_analyst[i]
        new = round(sp.target_cents * (1 + t))
        out.append(
            PublicEffect(sp.name, "target", t, f"{sp.name}: target {t:+.1%} to {money_words(new)}")
        )
    if e.sentiment:
        out.append(
            PublicEffect("the market", "sentiment", e.sentiment, f"sentiment {e.sentiment:+.1%}")
        )
    if e.credibility:
        out.append(
            PublicEffect(
                "credibility", "credibility", e.credibility, f"credibility {e.credibility:+.1f}"
            )
        )
    if e.guidance is not None:
        out.append(
            PublicEffect(
                "guidance",
                "guidance",
                0.0,
                f"guidance set: revenue {money_words(e.guidance[0])}",
            )
        )
    votes = tuple((meeting.speakers[i].name, v) for i, v in e.votes)
    return tuple(out), votes


def public(meeting: Meeting, mb: MeetingsBalance) -> PublicMeeting:
    items = {i.n: i for i in meeting.items}
    effects, votes = _effects(meeting)
    nxt = meeting.next_item
    return PublicMeeting(
        kind=meeting.kind,
        subject=meeting.subject,
        status=meeting.status,
        opened_turn=meeting.opened_turn,
        speakers=tuple(
            PublicSpeaker(
                s.key,
                s.kind,
                s.name,
                s.role,
                s.organisation,
                s.focus,
                s.confidence,
                s.rating,
                s.target_cents,
            )
            for s in meeting.speakers
        ),
        items=tuple(
            PublicItem(
                i.n,
                i.speaker,
                i.topic,
                i.title,
                i.question,
                i.facts,
                i.problem,
                i.figure.words if i.figure is not None else "",
                i.guidance,
            )
            for i in meeting.items
        ),
        answers=tuple(
            PublicAnswer(
                a.n,
                tuple(_move(meeting, items[a.n].facts, m) for m in a.claimed),
                tuple(_move(meeting, items[a.n].facts, m) for m in a.moves),
                reaction_of(raw_strength_public(meeting, items[a.n], a.moves, mb)),
                REACTIONS[reaction_of(raw_strength_public(meeting, items[a.n], a.moves, mb))],
                a.commitment.words if a.commitment is not None else "",
            )
            for a in meeting.answers
        ),
        next_item=nxt.n if nxt is not None and meeting.status == "open" else None,
        moves=tuple((k, MOVE_LABELS[k]) for k in MOVES[meeting.kind]),
        credibility=meeting.credibility,
        persona=meeting.persona,
        plan_subject=meeting.plan.subject if meeting.plan is not None else "",
        plan_facts=meeting.plan.facts if meeting.plan is not None else (),
        effects=effects,
        votes=votes,
        commitments=tuple(
            c.words for c in (meeting.effects.commitments if meeting.effects else ())
        ),
    )
