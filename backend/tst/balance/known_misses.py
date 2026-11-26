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


# M46 (v6 balance pass one): every entry M43 owned was traced on M46's code and moved to M57
# (v6 balance and polish), the next balance pass, with its reading; bounds tightened where the
# reading allows (docs/tasks/M46-v6-balance-pass-one.md, decision 10). V3.margin closed.
NEXT: Final = "M57"
KNOWN_MISSES: Final[tuple[KnownMiss, ...]] = (
    KnownMiss(
        target="V3.ai",  # docs/formulas.md 30.7 V3's AI arm: integrator_ai +3 to +10 points
        owner=NEXT,  # M46: from M43 (earlier M23, M28)
        # score: minus the margin gap (larger is worse); known while the AI integrator is no
        # more than 2 points below ai_regions (product manager, 2026-11-07)
        worse_than=0.02,
        reason="unmeasured on M46 and main (f4642ee8): ai_regions and integrator_ai go "
        "bankrupt on all 10 seeds (months 27-88), so the row has no margins and is skipped; "
        "AI models' D0 x0.19 (M43a) leaves an AI-first company too few customers",
    ),
    KnownMiss(
        target="V5.cells",  # 30.7 V5: >= 75% of (run, category, decade after 2020) cells
        owner=NEXT,  # M46: from M43 (earlier M23, M28)
        # score: the empty share; known while at most 30% empty (M46: was 40%)
        worse_than=0.30,
        reason="76% (steady_regions, passes) and 74% (research_heavy) on M46, counting only "
        "the categories startups are founded in (medical and space are scheduled only); "
        "long-lived startups hold rivals.startup.max_alive's places",
    ),
    KnownMiss(
        target="V5.cats",  # 30.7 V5: no category misses a decade in more than 2 of 10 runs
        owner=NEXT,  # M46: from M43 (earlier M23, M28)
        # score: the most runs a category-decade is empty in, as a share; known up to 65%
        # (M46: was 70%)
        worse_than=0.65,
        reason="cybersecurity 2020s empty in 5 of 8 research_heavy runs (62.5%), 4 of 10 "
        "steady_regions runs, on M46: as V5.cells",
    ),
    KnownMiss(
        target="I1",  # docs/formulas.md 43 I1: full_integrator margin - devices_regions, +3 to +10
        owner=NEXT,  # M46: from M43 (earlier M28)
        # score: minus the margin gap at year 30; known while the gap is at least -1.5 points
        # (M46: was -2.0)
        worse_than=0.015,
        reason="-1.1 pts at year 30 on M46 (weekly 45234561769): cost of goods is a small "
        "share of a 2039 group's revenue, so an own fab cannot move the margin",
    ),
    KnownMiss(
        target="V4.T1.2",  # formulas 51 T1: power_hyperscaler ARR / cloud_steady, 0.90-1.40x
        owner=NEXT,  # M46: from M43 (M35b)
        # score: |ratio - 1.15|; known down to 0.80x (score 0.35)
        worse_than=0.35,
        reason="0.82-0.93x by seed shard (M35b): the hyperscaler's ARR is its consumer app's, "
        "cloud earns little in every run, so power's edge shows mostly in capacity",
    ),
    KnownMiss(
        target="V4.T4",  # formulas 51 T4: the 2032 capacity live >= 12 months earlier
        owner=NEXT,  # M46: from M43 (M35b)
        # score: minus the median paired gap; known while the hyperscaler is never later
        worse_than=0.0,
        reason="+0 months on seeds 21-30 (M35b): in 6 of 10 runs grid power never binds "
        "before 2032, so both scripts' capacity goes live together; +12 over seeds 1-30",
    ),
    KnownMiss(
        target="M13b.T1",  # formulas 27.5 T1: a new product and region on >= 7 of 10 seeds
        owner=NEXT,  # M46: from M43 (M43a decision 10)
        # score: minus the seeds; known while at least 6 of 10
        worse_than=-6.0,
        reason="6/10 on M46 and M43a (main 7/10 before M43a): AI models' D0 x0.19 leaves "
        "about 5x fewer AI customers in the era window",
    ),
    KnownMiss(
        target="M22.T2.variant",  # formulas 39.4 T2: revenue lost with a variant 5-15%, every seed
        owner=NEXT,  # M46: from M43 (M43a decision 10)
        # score: the largest seed's loss; known while at most 21.5% (M46: was 22%, then 21%;
        # M54: 21.5%, PM ruling 2026-11-26)
        worse_than=0.215,
        reason="10.5-20.8% on M46 (unchanged since M43a): one seed out; the chip markets the "
        "variant sells into follow cloud and servers, both recalibrated before 2026. M54 "
        "currencies: East Asia's 2022-23 exchange rates lift every seed by 0.16-0.17 points "
        "(PM ruling 2026-11-26)",
    ),
    KnownMiss(
        target="V4.T1.1",  # formulas 51 T1: platform_owner ARR / devices_regions, 0.90-1.40x
        owner=NEXT,  # M46: from M43 (M43a decision 10)
        # score: |ratio - 1.15|; known down to 0.85x (score 0.30)
        worse_than=0.30,
        reason="0.89x on M43a (main 0.99x), December 2039: the ceilings from 2026 and the "
        "long-run decay from 2030 acting on the two strategies' markets differently",
    ),
    KnownMiss(
        target="V4",  # formulas 30.7 V4: ceo / steady_regions median ARR, 0.85-1.4x
        owner=NEXT,  # M46: from "v6 balance"
        # score: |ratio - 1.125|; known up to 1.47x (score 0.345; PM ruling 2026-11-21)
        worse_than=0.346,
        reason="1.46x on M46 (unchanged): the CEO's executives spend listed cash through "
        "their pitches (new products, regions) while steady_regions stays idle by design; "
        "M46's listed_planner deploys it (1.105x steady_regions), but V4 compares the idle "
        "script (decision 4)",
    ),
    KnownMiss(
        target="V4.T2",  # formulas 51 T2: no v4 strategy top on more than 4 of 10 seeds
        owner=NEXT,  # M46: from "v6 balance"
        # score: the most wins; known up to 5 of 10
        worse_than=5.0,
        reason="litho_bet 5/10 on M43 (main 3 on seeds 11-20 and 6 on 21-30): litho_bet "
        "(full_integrator plus its own lithography) already tops founder value on main",
    ),
    KnownMiss(
        target="M37.2069_month",  # tests/integration/test_m37_perf.py: 500 ms runner-adjusted
        owner="v6 performance",  # PM ruling 2026-11-21: v6's performance pass (not M46's)
        # score: the adjusted median in seconds; known up to 550 ms (PM ruling 2026-11-21)
        worse_than=0.550,
        reason="535 ms adjusted on M46 (main 467 ms the same day; 172 staff against 136): "
        "the listings leave a larger 2069 group, so the existing phases do more",
    ),
    KnownMiss(
        target="M54.T5",  # formulas 64.6 T5: an 80% hedge cuts yearly profit's spread >= 15%
        owner=NEXT,  # M54: carried, PM ruling 2026-11-26 (M54 decision 13)
        # score: the shortfall, 15% less the median cut; known while the median cut is >= 5%
        worse_than=0.10,
        reason="6.9% median (0.0-12.9%) on M54: forwards run at most 12 months (ADR-0025) and "
        "a year's total already averages a year of rates; M57 decides on 24-month forwards or "
        "the band for a 12-month hedge",
    ),
)

Verdict = Literal["ok", "printed", "known", "fail"]


@dataclass(frozen=True, slots=True)
class Reading:
    """A target a plain test asserts, judged like a report Row (M43a: M13, M13b, M22)."""

    target: str
    ok: bool
    score: float
    detail: str = ""


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
