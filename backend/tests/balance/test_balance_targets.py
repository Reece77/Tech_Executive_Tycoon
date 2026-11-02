"""docs/balance-targets.md, checked (M7a): the four v1 strategies on 10 seeds x 120 turns,
plus steady on easy and hard. Nightly (D4a); `make balance` prints the same table. Every
target with a band must hold; printed-only rows (T4d, T8) are not checked.

Since M10d (product manager, 2026-11-02) every target is a hard check: T2 and T3 pass with
blitzscale raising Series C and D and the growth-weighted ARR multiple; T5's blitzscale band
is 0-40% and T7's startup band 20-65%, with the reasons in docs/balance-targets.md.
"""

from __future__ import annotations

import os

import pytest

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
        if r.ok is False and r.target != "S2"
    ]
    assert not failed, "\n".join(failed)
