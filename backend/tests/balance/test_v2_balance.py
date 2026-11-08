"""docs/formulas.md 30.7 v2 balance targets (M15a): V1-V4 nightly over the nine strategies and
V3's AI arms on 10 seeds x 120 months; V1 over 30 seeds and V5's runs to December 2039 weekly
(.github/workflows/weekly.yml). A recorded known miss within its bound xfails."""

from __future__ import annotations

import os

import pytest

from tst.balance import v2
from tst.balance.known_misses import known_miss, verdict
from tst.balance.report import Row, _loaded, run_all, table
from tst.balance.strategies_v2 import ARMS, STRATEGIES


def _jobs() -> int:
    return int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))


def _check(rows: list[Row]) -> None:
    print("\n" + table(rows))
    failed = [f"{r.target} {r.measure}: {r.value} ({r.band})" for r in rows if verdict(r) == "fail"]
    assert not failed, "\n".join(failed)
    known = [known_miss(r.target) for r in rows if verdict(r) == "known"]
    if known:
        pytest.xfail("; ".join(f"KNOWN MISS ({k.owner}): {k.reason}" for k in known if k))


@pytest.mark.nightly
def test_v1_to_v4_ten_years() -> None:
    results = run_all(
        seeds=v2.SEEDS,
        strategies=[*STRATEGIES, *ARMS],
        difficulty_runs=False,
        jobs=_jobs(),
    )
    _check(v2.ten_year_rows(results))


@pytest.mark.nightly
@pytest.mark.weekly
def test_v1_over_30_seeds() -> None:
    results = run_all(
        seeds=v2.SEEDS_30, strategies=list(STRATEGIES), difficulty_runs=False, jobs=_jobs()
    )
    _check([v2.winners_row_30(results)])


@pytest.mark.nightly
@pytest.mark.weekly
def test_v5_thirty_years() -> None:
    runs = v2.run_long(jobs=_jobs())
    data = _loaded("data").game_data
    open_ = [
        c.key
        for c in data.categories
        if not (c.capacity_market or c.sells_units or c.assembly_market)
    ]
    scheduled = [c.key for c in data.categories if c.key not in open_]
    _check(v2.long_rows(runs, open_, scheduled))
