"""M27b's chain targets (a), (b) and (d), with (c)'s count (docs/formulas.md 40.13), weekly:
30-year runs (`make weekly-m27b`); tools/m27b_targets.py prints the same. Values recorded in
the M27b brief."""

from __future__ import annotations

import os

import pytest

from tst.balance import m27b


@pytest.mark.weekly
def test_m27b_chain_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    results = m27b.run(m27b.SEEDS, jobs)
    print(m27b.report(results))
    lo, hi = m27b.A_BAND
    assert lo <= m27b.target_a(results) <= hi  # (a) automated integrator vs the script
    assert min(r.owners for r in results if r.arm == "auto_15") >= m27b.MIN_OWNERS
    assert m27b.target_b(results) <= m27b.B_BELOW  # (b) score 8 at least 20% lower
    assert sum(r.never for r in results) == 0  # (c) no grey route or termination
    assert m27b.target_d(results) <= m27b.D_PROPOSALS  # (d) proposals a month
