"""docs/balance-targets.md, checked (M7a): the four v1 strategies on 10 seeds x 120 turns,
plus steady on easy and hard. Nightly (D4a); `make balance` prints the same table. Every
target with a band must hold; printed-only rows (T4d, T8) are not checked.

Since M10d (product manager, 2026-11-02) every target is a hard check: T2 and T3 pass with
blitzscale raising Series C and D and the growth-weighted ARR multiple; T5's blitzscale band
is 0-40% and T7's startup band 20-65%, with the reasons in docs/balance-targets.md. From M12a
(product manager, 2026-11-02) T2 is checked in its own xfail test and T5's bootstrap-frugal
band is 0-50%. From 2026-11-05 the recorded known misses (tst/balance/known_misses.py, read by
the balance runner too) are xfailed while within their "worse than" bound.
"""

from __future__ import annotations

import os

import pytest

from tst.balance.known_misses import KNOWN_MISSES, KnownMiss, verdict
from tst.balance.report import RunResult, evaluate, run_all, runs_table, table


@pytest.fixture(scope="module")
def results() -> list[RunResult]:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    return run_all(jobs=jobs)


@pytest.mark.nightly
def test_balance_targets(results: list[RunResult]) -> None:
    rows = evaluate(results)
    print("\n" + runs_table(results) + "\n\n" + table(rows))
    # S2 is gated by `make balance`, which runs alone (CI's nightly "balance" job); here the
    # balance run shares the machine with the other nightly tests, so S2 is printed only
    # (M10d: 13.6 worker-minutes alone, about 60 inside the parallel nightly).
    failed = [
        f"{r.target} {r.measure}: {r.value} ({r.band})"
        for r in rows
        if r.ok is False and r.target != "S2" and r.target not in {k.target for k in KNOWN_MISSES}
    ]
    assert not failed, "\n".join(failed)


@pytest.mark.nightly
@pytest.mark.parametrize("known", KNOWN_MISSES, ids=lambda k: k.target)
def test_known_misses(results: list[RunResult], known: KnownMiss) -> None:
    """Each recorded known miss on its own (T2 since M12a): passes if met, xfails while within
    its bound, fails if worse."""
    rows = [r for r in evaluate(results) if r.target == known.target]
    assert rows, f"no {known.target} row"
    worse = [f"{r.measure}: {r.value} ({r.band})" for r in rows if verdict(r) == "fail"]
    assert not worse, f"{known.target} is worse than its known-miss bound: {worse}"
    if any(verdict(r) == "known" for r in rows):
        pytest.xfail(f"KNOWN MISS ({known.owner}): {known.reason}")
