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
    # Target 4's margin gap (own GPU vs spot in 2023, >= +15 points) is NOT met: printed
    # above and reported to Reece (M12a brief, "Decisions made"). 2023 spot GPU compute is
    # $1,000 x the AI index 0.73, below a GPU data centre's $500 power alone; it needs a
    # design decision on the AI index or the GPU table, not a tuning of M12a's keys.
    assert sum(r.t5) >= 7  # target 5
    assert r.t6.half_formula >= 1.0 and r.t6.full_formula <= 0.2  # target 6
