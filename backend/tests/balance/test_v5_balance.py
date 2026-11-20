"""M43's v5 balance targets (tst.balance.v5): weekly (.github/workflows/weekly.yml). A recorded
known miss within its bound xfails. TST_V5_SEEDS ("1-10", "11-20", ...) picks the shard and
TST_V5_SAVE writes its runs as JSON (tools/v5_targets.py --load combines them);
TST_V5_DYNASTY=1 plays the v5 strategies with a family to December 2069 instead."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tst.balance import v5
from tst.balance.known_misses import known_miss, verdict
from tst.balance.report import table


def _seeds() -> list[int]:
    lo, _, hi = os.environ.get("TST_V5_SEEDS", "1-10").partition("-")
    return list(range(int(lo), int(hi or lo) + 1))


@pytest.mark.weekly
def test_v5_runs() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    dynasty = os.environ.get("TST_V5_DYNASTY") == "1"
    names = tuple(v5.V5) if dynasty else v5.PLAYED
    runs = v5.run_all(names, _seeds(), jobs=jobs, dynasty=dynasty)
    if path := os.environ.get("TST_V5_SAVE"):
        v5.save(runs, Path(path))
    print("\n" + v5.run_table(runs) + "\n\n" + v5.rung_table(runs))
    rows = v5.rows(runs)
    print("\n" + table(rows))
    failed = [f"{r.target} {r.measure}: {r.value} ({r.band})" for r in rows if verdict(r) == "fail"]
    assert not failed, "\n".join(failed)
    known = [known_miss(r.target) for r in rows if verdict(r) == "known"]
    if known:
        pytest.xfail("; ".join(f"KNOWN MISS ({k.owner}): {k.reason}" for k in known if k))


def test_a_dynasty_run_reads_the_familys_value() -> None:
    """The dynasty rows print the family's value (45.6), which a succession keeps: at turn 0 the
    founder heads the family, so it is at least the founder's own."""
    from tst.balance import m37

    game = m37._family_game(1)
    founder = game.founder_value[game.state.turn]
    assert founder > 0
    assert v5.family_value(game) >= founder
