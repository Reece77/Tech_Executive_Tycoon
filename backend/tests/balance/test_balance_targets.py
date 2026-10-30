"""docs/balance-targets.md, checked (M7a): the four v1 strategies on 10 seeds x 120 turns,
plus steady on easy and hard. Nightly (D4a); `make balance` prints the same table. Every
target with a band must hold; printed-only rows (T4d, T8) are not checked."""

from __future__ import annotations

import os

import pytest

from tst.balance.report import evaluate, run_all, runs_table, table


@pytest.mark.nightly
def test_balance_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    results = run_all(jobs=jobs)
    rows = evaluate(results)
    print("\n" + runs_table(results) + "\n\n" + table(rows))
    failed = [f"{r.target} {r.measure}: {r.value} ({r.band})" for r in rows if r.ok is False]
    assert not failed, "\n".join(failed)
