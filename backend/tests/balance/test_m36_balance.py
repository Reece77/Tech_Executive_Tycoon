"""docs/formulas.md 45.8 targets (M36), nightly; tools/m36_targets.py prints the same. Values
and the carried target 3 are recorded in the M36 brief ("Decisions made")."""

from __future__ import annotations

import os

import pytest

from tst.balance import m36


@pytest.mark.nightly
def test_45_8_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    r = m36.run(m36.SEEDS, jobs)
    print(m36.report(r))
    above, divorced, n = m36.target_2(r)
    assert above >= 8 and divorced >= 3 and n == len(m36.SEEDS)  # target 2
    _, _, gap = m36.target_3(r)
    assert gap > 0  # target 3, carried (the brief): upbringing helps, by less than 3 points
    _, _, ratio, _ = m36.target_4(r)
    assert 0.8 <= ratio <= 1.2  # target 4
    plain, trust, n5 = m36.target_5(r)
    assert plain * 2 >= n5 and trust <= 1  # target 5
