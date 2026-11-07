"""docs/formulas.md 32.7 targets (M24), nightly; tools/m24_targets.py prints the same. Values
recorded in the M24 brief ("Decisions made") and docs/balance-targets.md."""

from __future__ import annotations

import os

import pytest

from tst.balance import m24


@pytest.mark.nightly
def test_32_7_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    r = m24.run(m24.SEEDS, jobs)
    print(m24.report(r))
    assert m24.t1_burnouts(r) == 0  # target 1: the scripted strategies never burn out
    assert all(m is not None and 3 <= m <= 6 for m in m24.t2_all(r))  # target 2
    assert m24.t2_holiday_max(r) <= 1
    assert m24.t3_count(r, "blitzscale", m24.REAL) >= 6  # target 3
    assert m24.t3_count(r, "steady", m24.KIND) >= 6
    assert 0.20 <= m24.t4_cut(r) <= 0.40  # target 4
    assert 3 <= m24.t4_scandal_seeds(r) <= 7
    assert r.hiring <= 0.03 and 5 <= r.beloved <= 10  # target 5
