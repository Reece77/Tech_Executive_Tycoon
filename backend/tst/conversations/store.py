"""A negotiation to and from the JSON in `conversation.state` (exact: ints stay ints, floats
round-trip by repr)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from tst.sim.negotiation.models import (
    Counterpart,
    Hidden,
    Move,
    Negotiation,
    Round,
    TermSpec,
)


def dump(neg: Negotiation) -> dict[str, Any]:
    return asdict(neg)


def _tuple(v: Any) -> tuple[Any, ...]:
    return tuple(v) if v is not None else ()


def _move(d: dict[str, Any]) -> Move:
    return Move(d["kind"], d.get("term"), d.get("other"), d.get("fact"))


def _round(d: dict[str, Any]) -> Round:
    return Round(
        n=d["n"],
        offer=_tuple(d["offer"]),
        claimed=tuple(_move(m) for m in d["claimed"]),
        moves=tuple(_move(m) for m in d["moves"]),
        counter_before=_tuple(d["counter_before"]),
        counter=_tuple(d["counter"]),
        outcome=d["outcome"],
        reason=d["reason"],
        mood=d["mood"],
        relationship_change=d["relationship_change"],
    )


def load(d: dict[str, Any]) -> Negotiation:
    h = d["hidden"]
    return Negotiation(
        kind=d["kind"],
        subject=d["subject"],
        terms=tuple(TermSpec(**t) for t in d["terms"]),
        counterpart=Counterpart(**d["counterpart"]),
        facts=_tuple(d["facts"]),
        persona=_tuple(d["persona"]),
        hidden=Hidden(
            aspiration=_tuple(h["aspiration"]),
            reservation=_tuple(h["reservation"]),
            medians=_tuple(h["medians"]),
            patience=h["patience"],
            priorities=_tuple(h["priorities"]),
            openness=h["openness"],
            offsets=_tuple(h["offsets"]),
            skill=h["skill"],
        ),
        level=d["level"],
        patience_left=d["patience_left"],
        counter=_tuple(d["counter"]),
        opening=_tuple(d["opening"]),
        offer=None if d.get("offer") is None else _tuple(d["offer"]),
        rounds=tuple(_round(r) for r in d["rounds"]),
        status=d["status"],
        final=None if d.get("final") is None else _tuple(d["final"]),
        relationship_start=d["relationship_start"],
        relationship=d["relationship"],
        used_facts=_tuple(d["used_facts"]),
    )
