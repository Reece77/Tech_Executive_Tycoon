"""docs/formulas.md 22.7 targets 2-6 (M12a), nightly; tools/m12a_targets.py prints the same.
Values recorded in the M12a brief ("Decisions made")."""

from __future__ import annotations

import os

import pytest

from tst.balance import m12a


@pytest.mark.nightly
def test_22_7_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    r = m12a.run(m12a.SEEDS, jobs)
    print(m12a.report(r))
    assert r.t2.at_80 <= 0.70 and r.t2.at_40 >= 1.20  # target 2
    assert sum(x.reached for x in r.t3) >= 6  # target 3
    assert all(max(x.utilization) <= 1.0 + 1e-9 for x in r.t3)  # sold within the cap
    assert 0.20 <= r.t4.server_shortage <= 0.40  # target 4 (history)
    assert 0.40 <= r.t4.gpu_crunch <= 0.80
    # Target 4's margin gap at 0.45 x reference price (compute 38% of revenue on spot); at
    # reference prices it is about +7 points (printed). The GPU table keeps a data centre at
    # 40% use at 1.2 x spot or more in every build month (Reece, 2026-11-02).
    assert r.t4.margin_gap >= 0.15
    assert r.t4.gpu_40_worst >= 1.2
    assert sum(r.t5) >= 7  # target 5
    assert r.t6.half_formula >= 1.0 and r.t6.full_formula <= 0.2  # target 6
