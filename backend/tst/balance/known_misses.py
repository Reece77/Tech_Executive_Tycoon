"""Recorded known misses of the balance targets (docs/balance-targets.md, "Known misses"): the
one list read by tools/balance_runner.py (`make balance`, CI's nightly "balance" job) and by
the nightly pytest balance tests (their xfail).

A known miss names its target, the milestone that owns the fix and a "worse than" bound on
the target's score. A miss within the bound prints KNOWN MISS (<owner>) and does not fail the
job; a miss beyond it, or a miss of any target not listed, still fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, Protocol


@dataclass(frozen=True, slots=True)
class KnownMiss:
    target: str  # the Row.target it covers, e.g. "T2"
    owner: str  # the milestone that owns the fix, e.g. "M15"
    worse_than: float  # the miss stays known while the row's score is at most this
    reason: str


KNOWN_MISSES: Final[tuple[KnownMiss, ...]] = (
    KnownMiss(
        target="T2",
        owner="M15",
        # score: the most wins of any one strategy as a share of the seeds; 0.9 = 9/10, so
        # it fails only if one strategy wins every seed (Reece, 2026-11-05)
        worse_than=0.9,
        reason="steady wins 8/10 on main; M15's v2 strategies should split wins",
    ),
    KnownMiss(
        target="M10.T3",  # docs/formulas.md 20.5 target 3: covenants bite sometimes (20-60%)
        owner="M15",
        # score: the share of blitz_debt seeds that breach a covenant; known while below 90%,
        # M10's original measured value (product manager, 2026-11-04)
        worse_than=0.89,
        reason="70% of blitz_debt seeds breach on main over seeds 11-40 (60% on 1-10 was luck)",
    ),
)

Verdict = Literal["ok", "printed", "known", "fail"]


class _Judged(Protocol):
    @property
    def target(self) -> str: ...
    @property
    def ok(self) -> bool | None: ...
    @property
    def score(self) -> float | None: ...


def known_miss(target: str) -> KnownMiss | None:
    return next((k for k in KNOWN_MISSES if k.target == target), None)


def verdict(row: _Judged) -> Verdict:
    """ok, printed only, a known miss within its bound, or a failure."""
    if row.ok is None:
        return "printed"
    if row.ok:
        return "ok"
    known = known_miss(row.target)
    if known is not None and row.score is not None and row.score <= known.worse_than:
        return "known"
    return "fail"
