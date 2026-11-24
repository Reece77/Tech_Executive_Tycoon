"""A talk to and from the JSON in `conversation.state` (exact: ints stay ints, floats round-trip
by repr). The hidden part is stored with it and never read by the API."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from tst.sim.talks.models import (
    Answer,
    Counterpart,
    Effects,
    Move,
    PromiseOffer,
    Question,
    Subject,
    Talk,
    TalkHidden,
)


def dump(t: Talk) -> dict[str, Any]:
    return asdict(t)


def move(d: dict[str, Any]) -> Move:
    return Move(d["kind"])


def _offer(d: dict[str, Any] | None) -> PromiseOffer | None:
    return None if d is None else PromiseOffer(**d)


def _effects(d: dict[str, Any] | None) -> Effects | None:
    if d is None:
        return None
    persona = d.get("persona")
    return Effects(
        **{k: v for k, v in d.items() if k not in ("persona", "promise")},
        persona=None if persona is None else (str(persona[0]), float(persona[1])),
        promise=_offer(d.get("promise")),
    )


def load(d: dict[str, Any]) -> Talk:
    h = d["hidden"]
    return Talk(
        kind=d["kind"],
        company_id=d["company_id"],
        subject=Subject(**d["subject"]),
        opened_turn=d["opened_turn"],
        counterpart=Counterpart(**d["counterpart"]),
        questions=tuple(
            Question(
                n=q["n"],
                topic=q["topic"],
                title=q["title"],
                question=q["question"],
                facts=tuple(q["facts"]),
                offer=q["offer"],
                rival=q["rival"],
            )
            for q in d["questions"]
        ),
        hidden=TalkHidden(
            receptiveness=tuple(h["receptiveness"]),
            skill=h["skill"],
            traits=tuple((str(k), float(v)) for k, v in h["traits"]),
        ),
        audience=d["audience"],
        offer=_offer(d.get("offer")),
        delegate_id=d.get("delegate_id"),
        answers=tuple(
            Answer(
                n=a["n"],
                claimed=tuple(move(m) for m in a["claimed"]),
                moves=tuple(move(m) for m in a["moves"]),
                strength=a["strength"],
            )
            for a in d["answers"]
        ),
        status=d["status"],
        effects=_effects(d.get("effects")),
    )
