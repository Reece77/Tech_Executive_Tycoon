"""M35b's v4 balance targets (tst.balance.v4): weekly (.github/workflows/weekly.yml). A recorded
known miss within its bound xfails. TST_V4_SEEDS ("1-10", "11-20", ...) picks the shard and
TST_V4_SAVE writes its runs as JSON (tools/v4_targets.py --load combines them)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tst.balance import v4
from tst.balance.known_misses import known_miss, verdict
from tst.balance.report import table


def _seeds() -> list[int]:
    lo, _, hi = os.environ.get("TST_V4_SEEDS", "1-10").partition("-")
    return list(range(int(lo), int(hi or lo) + 1))


@pytest.mark.weekly
def test_v4_thirty_years() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    runs = v4.run_all(v4.PLAYED, _seeds(), jobs=jobs)
    if path := os.environ.get("TST_V4_SAVE"):
        v4.save(runs, Path(path))
    print("\n" + v4.run_table(runs) + "\n\n" + v4.rung_table(runs))
    rows = v4.rows(runs)
    print("\n" + table(rows))
    failed = [f"{r.target} {r.measure}: {r.value} ({r.band})" for r in rows if verdict(r) == "fail"]
    assert not failed, "\n".join(failed)
    known = [known_miss(r.target) for r in rows if verdict(r) == "known"]
    if known:
        pytest.xfail("; ".join(f"KNOWN MISS ({k.owner}): {k.reason}" for k in known if k))
