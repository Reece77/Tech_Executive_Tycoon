"""Validating the LLM's answers (ADR-0005, ADR-0023 section 2): untrusted JSON in, the closed
move set out. Anything that does not fit becomes `neutral`; a reply that names a number the
decision did not give, or runs long, is replaced by the template's.

M57r-B (review 10 item 21): a reply's money and percentages are compared with their units ("12"
from "12 months" no longer licenses "$12"), amounts in words are refused, and the wording may
not state an outcome the engine did not decide ("we have a deal" on a walk-away)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, Literal

from tst.sim.negotiation.config import MOVE_KINDS
from tst.sim.negotiation.models import Move

NEUTRAL = (Move("neutral"),)
NUMBER = re.compile(r"\d[\d,.]*")
MONEY = re.compile(r"\$\s?(\d[\d,.]*)\s?(k|m|bn|b|thousand|million|billion)?\b", re.IGNORECASE)
PERCENT = re.compile(r"(\d[\d,.]*)\s?(%|percent\b|per cent\b)", re.IGNORECASE)
AMOUNT_WORDS = re.compile(
    r"\b(hundred|thousand|million|billion|trillion|dozen)s?\b|"
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety)\s+(percent|per cent|dollars?|bucks|k)\b",
    re.IGNORECASE,
)
type OutcomeClass = Literal["agreed", "walked", "open", "any"]
# What a reply may not say unless the engine decided it (word boundaries, any case)
CLAIMS: dict[str, re.Pattern[str]] = {
    "agreed": re.compile(
        r"\b(we have a deal|it'?s a deal|deal done|you have a deal|we('re| are) agreed|"
        r"agreed|we accept|i accept|accepted|let'?s sign|shake on it|signed)\b",
        re.IGNORECASE,
    ),
    "walked": re.compile(
        r"\b(walk(ing)? away|we('re| are) done|no deal|we('re| are) out|end(ing)? (these|the) "
        r"talks|goodbye|we('re| are) leaving)\b",
        re.IGNORECASE,
    ),
}
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


def _norm(n: str) -> str:
    return n.rstrip(".,").replace(",", "")


def _money(text: str) -> set[tuple[str, str]]:
    return {(_norm(m[1]), (m[2] or "").lower()) for m in MONEY.finditer(text)}


def _percents(text: str) -> set[str]:
    return {_norm(m[1]) for m in PERCENT.finditer(text)}


def reply_ok(
    text: object, allowed: Iterable[str], words: int, outcome: OutcomeClass = "any"
) -> str | None:
    """The reply if it is plain text within the word limit, names only allowed numbers
    (16.5's allowlist: those in the decision and the public facts), money and percentages
    only as the allowed text gives them (with their units), no amount in words, and no outcome
    but `outcome` ("any": no outcome check)."""
    if not isinstance(text, str):
        return None
    clean = " ".join(text.split())
    if not clean or len(clean.split()) > words:
        return None
    given = list(allowed)
    permitted: set[str] = set()
    for a in given:
        permitted |= _numbers(a)
    if not _numbers(clean) <= permitted:
        return None
    money: set[tuple[str, str]] = set().union(*(_money(a) for a in given)) if given else set()
    pct: set[str] = set().union(*(_percents(a) for a in given)) if given else set()
    if not _money(clean) <= money or not _percents(clean) <= pct:
        return None
    if AMOUNT_WORDS.search(clean):
        return None
    if outcome != "any":
        for claim, pattern in CLAIMS.items():
            if claim != outcome and pattern.search(clean):
                return None
    return clean
