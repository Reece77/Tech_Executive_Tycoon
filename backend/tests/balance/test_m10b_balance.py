"""docs/formulas.md 23.7 target 1 (M10b), nightly; tools/m10b_targets.py prints the same.
Values recorded in the M10b brief and docs/balance-targets.md."""

from __future__ import annotations

import os

import pytest

from tst.balance import m10b

CRITICAL_GAP = 6


@pytest.mark.nightly
def test_1_critical_events_for_grown_companies() -> None:
    runs = m10b.run(m10b.SEEDS, int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1))))
    for r in runs:
        print(
            f"seed {r.seed:2d}: {r.big_months} months with 20+ staff, {r.big_criticals} critical "
            f"in them; all critical {list(r.criticals)}; shortest gap {r.shortest_gap}"
        )
    value = m10b.per_window(runs)
    print(f"23.7 target 1: {value:.2f} critical events per 18 months with 20+ staff (needs >= 1)")
    assert all(r.shortest_gap is None or r.shortest_gap >= CRITICAL_GAP for r in runs)
    assert sum(r.big_months for r in runs) > 0
    assert value >= 1.0
