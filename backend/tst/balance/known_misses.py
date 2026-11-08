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
        target="V3.ai",  # docs/formulas.md 30.7 V3's AI arm: integrator_ai +3 to +10 points
        owner="M23",
        # score: minus the margin gap (larger is worse); known while the AI integrator is no
        # more than 2 points below ai_regions (product manager, 2026-11-07)
        worse_than=0.02,
        reason="+0.7 pts in M15a: an AI-models company is about $7M ARR at year 10 (2020)",
    ),
    KnownMiss(
        target="V5.cells",  # 30.7 V5: >= 75% of (run, category, decade after 2020) cells
        owner="M23",
        # score: the empty share; known while at most 40% empty (product manager,
        # 2026-11-07, fifth round: owned by M23, fails below 60%)
        worse_than=0.40,
        reason="68-77% in M15a: long-lived startups hold rivals.startup.max_alive's places",
    ),
    KnownMiss(
        target="V5.cats",  # 30.7 V5: no category misses a decade in more than 2 of 10 runs
        owner="M23",
        # score: the most runs a category-decade is empty in, as a share; known up to 70%
        worse_than=0.70,
        reason="2030s category-decades empty in up to 6 of 10 runs (M15a): as V5.cells",
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
