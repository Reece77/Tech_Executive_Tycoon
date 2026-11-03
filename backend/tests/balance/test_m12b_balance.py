"""docs/formulas.md 26.6 targets 2-6 (M12b), nightly; tools/m12b_targets.py prints the same.
Values recorded in docs/balance-targets.md (M12b) and the M12b brief."""

from __future__ import annotations

import os

import pytest

from tst.balance import m12b


@pytest.mark.nightly
def test_26_6_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    r = m12b.run(m12b.SEEDS, jobs)
    print(m12b.report(r))
    assert sum(0.30 <= x.margin <= 0.45 for x in r.t2) >= 6  # target 2
    assert r.t3.at_75 <= 0.70 and r.t3.at_30 >= 1.30  # target 3
    assert all(g >= 8 for g in r.t4_gaps)  # target 4 (own SoC)
    assert r.t4b[0] >= 0.20  # target 4 (GPU capex)
    assert all(0.15 <= x.fewer <= 0.35 for x in r.t5)  # target 5
    assert sum(s >= 0.5 for s in r.t6) >= 7  # target 6
