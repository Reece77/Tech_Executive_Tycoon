"""docs/balance-targets.md, checked (M7a): the four v1 strategies on 10 seeds x 120 turns,
plus steady on easy and hard. Nightly (D4a); `make balance` prints the same table. Every
target with a band must hold; printed-only rows (T4d, T8) are not checked.

T2 is its own test, marked as an expected failure (M7c sub-task 0, Reece 2026-10-31): after
M8's script changes steady wins 10/10 seeds; the miss is recorded for M15. T3 for
blitzscale is the same (M8r, Reece 2026-10-31): once a poached executive left their seat
(Codex review 1 finding 3), blitzscale succeeded 1/10, and 2/10 with the exec salary on
appointment. Every other target stays a hard check.
"""

from __future__ import annotations

import os

import pytest

from tst.balance.report import RunResult, evaluate, run_all, runs_table, table

T2 = "T2"
T2_REASON = "recorded miss: steady wins 10/10 after M8; rebalance in M15"
T3_BLITZ = ("T3", "blitzscale succeeds")
T3_REASON = (
    "recorded miss: blitzscale succeeds 2/10 (needs 3) once poached executives leave their "
    "seats (M8r); rebalance in M15"
)


def _t3_blitz(row: object) -> bool:
    return (getattr(row, "target", None), getattr(row, "measure", None)) == T3_BLITZ


@pytest.fixture(scope="module")
def results() -> list[RunResult]:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    return run_all(jobs=jobs)


@pytest.mark.nightly
def test_balance_targets(results: list[RunResult]) -> None:
    rows = evaluate(results)
    print("\n" + runs_table(results) + "\n\n" + table(rows))
    failed = [
        f"{r.target} {r.measure}: {r.value} ({r.band})"
        for r in rows
        if r.ok is False and r.target != T2 and not _t3_blitz(r)
    ]
    assert not failed, "\n".join(failed)


@pytest.mark.nightly
@pytest.mark.xfail(strict=False, reason=T2_REASON)
def test_balance_t2_wins(results: list[RunResult]) -> None:
    rows = [r for r in evaluate(results) if r.target == T2]
    assert rows
    failed = [f"{r.measure}: {r.value} ({r.band})" for r in rows if r.ok is False]
    assert not failed, "\n".join(failed)


@pytest.mark.nightly
@pytest.mark.xfail(strict=False, reason=T3_REASON)
def test_balance_t3_blitzscale(results: list[RunResult]) -> None:
    rows = [r for r in evaluate(results) if _t3_blitz(r)]
    assert rows
    assert all(r.ok is not False for r in rows), [f"{r.value} ({r.band})" for r in rows]
