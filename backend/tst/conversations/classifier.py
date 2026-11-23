"""Validating the LLM's answers (ADR-0005, ADR-0023 section 2): untrusted JSON in, the closed
move set out. Anything that does not fit becomes `neutral`; a reply that names a number the
decision did not give, or runs long, is replaced by the template's."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from tst.sim.negotiation.config import MOVE_KINDS
from tst.sim.negotiation.models import Move

NEUTRAL = (Move("neutral"),)
NUMBER = re.compile(r"\d[\d,.]*")
MAX_INDEX = 16  # tunable-exempt: no deal has more terms or facts than this


def _index(v: Any) -> int | None:
    if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v < MAX_INDEX:
        return None
    return v


def moves_from(content: object, max_moves: int) -> tuple[tuple[Move, ...], bool]:
    """(moves, valid): the scored moves, or `neutral` with valid False if the JSON is not the
    schema's. The engine still checks each move against the offer and the facts."""
    if not isinstance(content, dict) or set(content) != {"moves"}:
        return NEUTRAL, False
    raw = content["moves"]
    if not isinstance(raw, list) or not raw:
        return NEUTRAL, False
    out: list[Move] = []
    for item in raw[:max_moves]:
        if not isinstance(item, dict) or not set(item) <= {"move", "term", "other", "fact"}:
            return NEUTRAL, False
        kind = item.get("move")
        if kind not in MOVE_KINDS:
            return NEUTRAL, False
        out.append(
            Move(
                kind,
                _index(item.get("term")),
                _index(item.get("other")),
                _index(item.get("fact")),
            )
        )
    return tuple(out), True


def suggestions_from(content: object, n: int, max_chars: int) -> list[str] | None:
    if not isinstance(content, dict) or set(content) != {"replies"}:
        return None
    raw = content["replies"]
    if not isinstance(raw, list):
        return None
    out = [" ".join(str(r).split()) for r in raw if isinstance(r, str) and r.strip()]
    out = [r for r in out if len(r) <= max_chars]
    return out[:n] if len(out) >= n else None


def _numbers(text: str) -> set[str]:
    return {m.rstrip(".,") for m in NUMBER.findall(text)}


def reply_ok(text: object, allowed: Iterable[str], words: int) -> str | None:
    """The reply if it is plain text within the word limit and names only allowed numbers
    (16.5's allowlist: those in the decision and the public facts)."""
    if not isinstance(text, str):
        return None
    clean = " ".join(text.split())
    if not clean or len(clean.split()) > words:
        return None
    permitted: set[str] = set()
    for a in allowed:
        permitted |= _numbers(a)
    if not _numbers(clean) <= permitted:
        return None
    return clean
