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


_EARLIER: Final[tuple[KnownMiss, ...]] = (
    KnownMiss(
        target="V3.ai",  # docs/formulas.md 30.7 V3's AI arm: integrator_ai +3 to +10 points
        owner="M43",  # M43 sub-task 1: moved from the finished M28 (owner M23, then M28)
        # score: minus the margin gap (larger is worse); known while the AI integrator is no
        # more than 2 points below ai_regions (product manager, 2026-11-07)
        worse_than=0.02,
        reason="+0.7 pts in M15a: an AI-models company is about $7M ARR at year 10 (2020)",
    ),
    KnownMiss(
        target="V5.cells",  # 30.7 V5: >= 75% of (run, category, decade after 2020) cells
        owner="M43",  # M43 sub-task 1: moved from the finished M28 (owner M23, then M28)
        # score: the empty share; known while at most 40% empty (product manager,
        # 2026-11-07, fifth round: owned by M23, fails below 60%)
        worse_than=0.40,
        reason="68-77% in M15a: long-lived startups hold rivals.startup.max_alive's places",
    ),
    KnownMiss(
        target="V5.cats",  # 30.7 V5: no category misses a decade in more than 2 of 10 runs
        owner="M43",  # M43 sub-task 1: moved from the finished M28 (owner M23, then M28)
        # score: the most runs a category-decade is empty in, as a share; known up to 70%
        worse_than=0.70,
        reason="2030s category-decades empty in up to 6 of 10 runs (M15a): as V5.cells",
    ),
    KnownMiss(
        target="I1",  # docs/formulas.md 43 I1: full_integrator margin - devices_regions, +3 to +10
        owner="M43",  # M43 sub-task 1: moved from the finished M28
        # score: minus the margin gap at year 30; known while the gap is at least -2.0 points,
        # the year-30 reading on the combined code (-0.0, weekly 43381860624) minus 2 (product
        # manager, 2026-11-12)
        worse_than=0.020,
        reason="-0.0 pts at year 30 (M23b): cost of goods is 0.2-0.3% of a 2039 group's revenue; "
        "M28's supply-driven prices from 2026 change the fab's economics",
    ),
    KnownMiss(
        target="V4.T1.2",  # formulas 51 T1: power_hyperscaler ARR / cloud_steady, 0.90-1.40x
        owner="M43",  # M35b (docs/tasks/M35b-v4-balance.md, Decisions): v5's balance pass
        # score: |ratio - 1.15|; known down to 0.80x (score 0.35): the three shards on the
        # final scripts read 0.93x, 0.89x and 0.82x (weekly 43852709862, 43893475146)
        worse_than=0.35,
        reason="0.82-0.93x by seed shard (M35b): the hyperscaler's ARR is its consumer app's, "
        "cloud earns little in every run, so power's edge shows mostly in capacity",
    ),
    KnownMiss(
        target="V4.T4",  # formulas 51 T4: the 2032 capacity live >= 12 months earlier
        owner="M43",  # M35b (docs/tasks/M35b-v4-balance.md, Decisions)
        # score: minus the median paired gap; known while the hyperscaler is never later
        # (gap >= 0): +36, +24 and +0 months by shard, +12 pooled over seeds 1-30
        worse_than=0.0,
        reason="+0 months on seeds 21-30 (M35b): in 6 of 10 runs grid power never binds "
        "before 2032, so both scripts' capacity goes live together; +12 over seeds 1-30",
    ),
    KnownMiss(
        target="M13b.T1",  # formulas 27.5 T1: a new product and region on >= 7 of 10 seeds
        owner="M43",  # PM, 2026-11-18 (M43a brief, decision 10)
        # score: minus the seeds; known while at least 6 of 10
        worse_than=-6.0,
        reason="6/10 on M43a (main 7/10): AI models' D0 x0.19 leaves about 5x fewer AI "
        "customers in the era window",
    ),
    KnownMiss(
        target="M22.T2.variant",  # formulas 39.4 T2: revenue lost with a variant 5-15%, every seed
        owner="M43",  # PM, 2026-11-18 (M43a brief, decision 10)
        # score: the largest seed's loss; known while at most 22%
        worse_than=0.22,
        reason="10.5-20.8% on M43a (main 10.5-10.8%): one seed out; the chip markets the variant "
        "sells into follow cloud and servers, both recalibrated before 2026",
    ),
    KnownMiss(
        target="V2.wins",  # formulas 30.7 V2: research_heavy wins at most 4 of 10
        owner="M43",  # PM, 2026-11-18 (M43a brief, decision 10)
        # score: research_heavy's wins out of 10; known while at most 5
        worse_than=5.0,
        reason="5/10 on M43a (main <= 4): measured before 2026, where only M43a's four "
        "recalibrations (AI models, cloud, developer tools, servers) act",
    ),
    KnownMiss(
        target="V3.margin",  # formulas 30.7 V3: integrator - steady_regions margin -1 pt or more
        owner="M43",  # PM, 2026-11-18 (M43a brief, decision 10)
        # score: minus the margin gap; known while the gap is at least -2.0 points
        worse_than=0.020,
        reason="-1.4 pts on M43a (62.1% vs 63.6%; main passes): before 2026, as V2.wins",
    ),
    KnownMiss(
        target="V4.T1.1",  # formulas 51 T1: platform_owner ARR / devices_regions, 0.90-1.40x
        owner="M43",  # PM, 2026-11-18 (M43a brief, decision 10)
        # score: |ratio - 1.15|; known down to 0.85x (score 0.30)
        worse_than=0.30,
        reason="0.89x on M43a (main 0.99x), December 2039: not traced; likely the ceilings from "
        "2026 and the long-run decay from 2030 acting on the two strategies' markets differently",
    ),
)

# M43 (PM ruling 2026-11-20): the guards the real-listings IPO floor (25.1: $241M x
# economy_scale.money, $20.5M game ARR) still moves are known misses owned by v6's first balance
# pass, each bounded at the branch's reading
V6_BALANCE: Final = "v6 balance"
KNOWN_MISSES: Final[tuple[KnownMiss, ...]] = (
    *_EARLIER,
    KnownMiss(
        target="V2",  # formulas 30.7 V2: research_heavy / steady_regions median ARR, 1.0-1.4x
        owner=V6_BALANCE,
        # score: |ratio - 1.2|; known up to 1.42x (score 0.22), the M43 branch's reading
        worse_than=0.221,
        reason="1.42x on M43 (main in band): with the IPO floor at the game's economy every script "
        "lists in 2015-16 with $440-770M of cash; steady_regions hires at most two a month, so "
        "its cash sits idle while research_heavy's research unit turns it into growth",
    ),
    KnownMiss(
        target="V4",  # formulas 30.7 V4: ceo / steady_regions median ARR, 0.85-1.4x
        owner=V6_BALANCE,
        # score: |ratio - 1.125|; known up to 1.45x (score 0.325), the M43 branch's reading
        worse_than=0.326,
        reason="1.45x on M43 (main in band): as V2, the CEO spends the listing's cash and "
        "steady_regions' two hires a month do not",
    ),
    KnownMiss(
        target="V4.T2",  # formulas 51 T2: no v4 strategy top on more than 4 of 10 seeds
        owner=V6_BALANCE,
        # score: the most wins; known up to 5 of 10, the M43 branch's reading on seeds 11-20
        # and 21-30 (main: 3 on 11-20, 6 on 21-30)
        worse_than=5.0,
        reason="litho_bet 5/10 on M43 (main 3 on seeds 11-20 and 6 on 21-30): litho_bet "
        "(full_integrator plus its own lithography) already tops founder value on main; the "
        "IPO floor moves which seeds it wins, not how often",
    ),
    KnownMiss(
        target="M37.2069_month",  # tests/integration/test_m37_perf.py: 500 ms runner-adjusted
        owner=V6_BALANCE,
        # score: the adjusted median in seconds; known up to the M43 branch's reading
        worse_than=0.527,
        reason="526 ms adjusted on M43 (main passes): no M43 step in the profile (markets 27%, "
        "state sync 22%, rival decisions 11% of a 2069 month); the listings from 2015 leave a "
        "larger 2069 group (157 staff), so the existing phases do more",
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
