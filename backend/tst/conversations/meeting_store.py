"""A meeting to and from the JSON in `conversation.state` (exact: ints stay ints, floats
round-trip by repr). The hidden part is stored with it and never read by the API."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from tst.sim.meetings.models import (
    Answer,
    Commitment,
    Effects,
    Figure,
    Item,
    Meeting,
    MeetingHidden,
    Move,
    Plan,
    Speaker,
)


def dump(m: Meeting) -> dict[str, Any]:
    return asdict(m)


def _t(v: Any) -> tuple[Any, ...]:
    return tuple(v) if v is not None else ()


def move(d: dict[str, Any]) -> Move:
    return Move(d["kind"], d.get("fact"))


def _commitment(d: dict[str, Any] | None) -> Commitment | None:
    return None if d is None else Commitment(**d)


def _answer(d: dict[str, Any]) -> Answer:
    return Answer(
        n=d["n"],
        claimed=tuple(move(m) for m in d["claimed"]),
        moves=tuple(move(m) for m in d["moves"]),
        strength=d["strength"],
        commitment=_commitment(d.get("commitment")),
        guidance_change=d.get("guidance_change", 0),
        reaffirmed=d.get("reaffirmed", False),
        credibility=d.get("credibility", 0.0),
    )


def _item(d: dict[str, Any]) -> Item:
    fig = d.get("figure")
    return Item(
        n=d["n"],
        speaker=d["speaker"],
        topic=d["topic"],
        title=d["title"],
        question=d["question"],
        facts=_t(d["facts"]),
        problem=d["problem"],
        figure=None if fig is None else Figure(**fig),
        guidance=d["guidance"],
    )


def _effects(d: dict[str, Any] | None) -> Effects | None:
    if d is None:
        return None
    g = d.get("guidance")
    return Effects(
        confidence=tuple((int(s), float(v)) for s, v in d["confidence"]),
        sentiment=d["sentiment"],
        targets=tuple((int(i), float(v)) for i, v in d["targets"]),
        credibility=d["credibility"],
        commitments=tuple(Commitment(**c) for c in d["commitments"]),
        guidance=None if g is None else (int(g[0]), int(g[1])),
        votes=tuple((int(i), bool(v)) for i, v in d["votes"]),
    )


def load(d: dict[str, Any]) -> Meeting:
    h = d["hidden"]
    plan = d.get("plan")
    base = d.get("guidance_base")
    return Meeting(
        kind=d["kind"],
        company_id=d["company_id"],
        subject=d["subject"],
        opened_turn=d["opened_turn"],
        period_turn=d["period_turn"],
        speakers=tuple(Speaker(**s) for s in d["speakers"]),
        items=tuple(_item(i) for i in d["items"]),
        hidden=MeetingHidden(
            priorities=tuple(tuple(p) for p in h["priorities"]),
            receptiveness=_t(h["receptiveness"]),
            skill=h["skill"],
        ),
        persona=_t(d["persona"]),
        credibility=d["credibility"],
        guidance_base=None if base is None else (int(base[0]), int(base[1])),
        plan=None
        if plan is None
        else Plan(plan["kind"], plan["subject"], _t(plan["facts"]), plan["economics"]),
        answers=tuple(_answer(a) for a in d["answers"]),
        status=d["status"],
        effects=_effects(d.get("effects")),
    )
