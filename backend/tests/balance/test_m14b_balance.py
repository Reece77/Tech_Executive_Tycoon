"""docs/formulas.md 29.7 targets 2-5 (M14b), nightly; tools/m14b_targets.py prints the same.
Values recorded in the M14b brief ("Decisions made") and docs/balance-targets.md."""

from __future__ import annotations

import os

import pytest

from tst.balance import m14b


@pytest.mark.nightly
def test_29_7_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    r = m14b.run(m14b.SEEDS, jobs)
    print(m14b.report(r))
    assert 5 <= m14b.t2_brand(r, "kept") <= 15  # target 2
    assert -25 <= m14b.t2_brand(r, "broken") <= -10
    assert 0.05 <= m14b.t2_sentiment(r) <= 0.15
    assert m14b.t3_moments(r) <= 6  # target 3
    assert 5 <= m14b.t4_rivalries(r) <= 9  # target 4
    assert 0.20 <= m14b.t4_lift(r) <= 0.60
    assert 0.30 <= m14b.t5_shorter(r) <= 0.50  # target 5
