"""M57's v6 strategy targets (tst.balance.v6): weekly (.github/workflows/weekly.yml). A recorded
known miss within its bound xfails. TST_V6_SEEDS ("1-20", "1-5", ...) picks the seeds and
TST_V6_SAVE writes the runs as JSON (tools/v6_targets.py --load combines shards)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tst.balance import v6
from tst.balance.known_misses import known_miss, verdict
from tst.balance.report import table


def _seeds() -> list[int]:
    lo, _, hi = os.environ.get("TST_V6_SEEDS", "1-20").partition("-")
    return list(range(int(lo), int(hi or lo) + 1))


@pytest.mark.weekly
def test_v6_strategies() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    runs = v6.run_all(v6.PLAYED, _seeds(), jobs=jobs)
    if path := os.environ.get("TST_V6_SAVE"):
        v6.save(runs, Path(path))
    print("\n" + v6.run_table(runs) + "\n\n" + v6.strategy_table(runs))
    rows = v6.rows(runs)
    print("\n" + table(rows))
    failed = [f"{r.target} {r.measure}: {r.value} ({r.band})" for r in rows if verdict(r) == "fail"]
    assert not failed, "\n".join(failed)
    known = [known_miss(r.target) for r in rows if verdict(r) == "known"]
    if known:
        pytest.xfail("; ".join(f"KNOWN MISS ({k.owner}): {k.reason}" for k in known if k))


def _run(strategy: str, seed: int, score_1: int, score_30: int) -> v6.V6Run:
    return v6.V6Run(strategy, seed, score_1, score_30, 0, {})


def test_the_rows_read_growth_and_the_field_median() -> None:
    """T1 reads each v6 strategy's median growth; T2 its median year-30 score over the median of
    the field strategies' medians, failing above 1.4x."""
    runs = [_run(s, seed, 100, 500) for s in v6.FIELD for seed in (1, 2)]
    runs += [_run("media_studio", 3, 100, 900)]
    t1 = {r.target: r for r in v6.t1_rows(runs)}
    assert all(r.ok for r in t1.values())
    assert v6.field_median(runs) == 500
    t2 = {r.target: r for r in v6.t2_rows(runs)}
    assert all(r.ok for r in t2.values())
    runs = [r for r in runs if r.strategy not in ("bank_group", "telecom_operator")]
    runs += [_run("bank_group", seed, 600, 800) for seed in (1, 2)]
    runs += [_run("telecom_operator", seed, 600, 0) for seed in (1, 2)]  # failed runs score 0
    t1 = {r.target: r for r in v6.t1_rows(runs)}
    t2 = {r.target: r for r in v6.t2_rows(runs)}
    assert t1["V6.T1.bank_group"].ok and not t2["V6.T2.bank_group"].ok  # 800 / 500 = 1.6x
    assert not t1["V6.T1.telecom_operator"].ok and t2["V6.T2.telecom_operator"].ok
