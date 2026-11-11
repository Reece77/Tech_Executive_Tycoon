"""M23b's v3 balance targets (tst.balance.v3): weekly (.github/workflows/weekly.yml). A recorded
known miss within its bound xfails."""

from __future__ import annotations

import os

import pytest

from tst.balance import v3
from tst.balance.known_misses import known_miss, verdict
from tst.balance.report import Row, table


def _jobs() -> int:
    return int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))


def _check(rows: list[Row]) -> None:
    print("\n" + table(rows))
    failed = [f"{r.target} {r.measure}: {r.value} ({r.band})" for r in rows if verdict(r) == "fail"]
    assert not failed, "\n".join(failed)
    known = [known_miss(r.target) for r in rows if verdict(r) == "known"]
    if known:
        pytest.xfail("; ".join(f"KNOWN MISS ({k.owner}): {k.reason}" for k in known if k))


@pytest.mark.weekly
def test_v3_shocks() -> None:
    _check(v3.shock_rows(v3.lithium_rise(), [v3.gallium_run(s) for s in v3.SEEDS]))


@pytest.mark.weekly
def test_v3_integration_twenty_years() -> None:
    runs = v3.run_all(v3.PLAYED_20, v3.SEEDS, v3.YEARS_20, jobs=_jobs())
    print("\n" + v3.run_table(runs))
    _check(v3.integration_rows(runs))


@pytest.mark.weekly
def test_v3_chain_thirty_years() -> None:
    runs = v3.run_all(v3.LONG_STRATEGIES, v3.SEEDS, v3.LONG_TURNS, jobs=_jobs())
    print("\n" + v3.run_table(runs) + "\n\n" + v3.rung_table(runs))
    _check(v3.fab_rows(runs) + v3.long_rows(runs))
