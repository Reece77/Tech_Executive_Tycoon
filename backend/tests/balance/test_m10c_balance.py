"""docs/formulas.md 24.5 targets 1-4 (M10c), nightly; tools/m10c_targets.py prints the same.
Values recorded in the M10c brief and docs/balance-targets.md."""

from __future__ import annotations

import os

import pytest

from tst.balance import m10c


@pytest.mark.nightly
def test_24_5_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    runs = m10c.run(m10c.SEEDS, jobs)
    print(m10c.report(runs))
    delegated = m10c.arm(runs, "delegated")
    assert len(delegated) >= 5  # enough seeds reach stage 3 to compare
    assert 0.85 <= m10c.median_ratio(runs, "delegated", "steady") <= 1.15  # target 1
    assert max(r.longest_below for r in delegated) <= 2
    assert m10c.median_ratio(runs, "delegated", "delegated_8") >= 1.15  # target 2
    assert all(r.builders_max <= r.builder_cap for r in delegated)  # target 3
    assert all(r.sellers_max <= r.seller_cap for r in delegated)
    assert all(m10c.mean_coverage_gap(r, 1.0) <= 0.1 for r in delegated)
    assert sum(r.energy_unspent for r in delegated) / len(delegated) >= 0.6  # target 4
