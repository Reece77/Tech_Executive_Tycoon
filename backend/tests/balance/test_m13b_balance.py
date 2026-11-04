"""docs/formulas.md 27.5 targets 1-5 (M13b), nightly; tools/m13b_targets.py prints the same.
Values recorded in the M13b brief and docs/balance-targets.md."""

from __future__ import annotations

import os

import pytest

from tst.balance import m13b


@pytest.mark.nightly
def test_27_5_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    results = m13b.run(m13b.SEEDS, jobs)
    print(m13b.report(results))
    assert len(m13b.arm(results, "pitches")) >= 7  # enough seeds reach stage 3
    assert m13b.target_1(results) >= 7  # a new product and a new region
    assert m13b.target_2(results) >= 1.10  # and it pays
    good, weak = m13b.target_3(results)
    assert good - weak >= 0.15  # good executives pitch better
    assert m13b.target_4(results) <= 8  # the inbox stays calm
    n, _ = m13b.target_5(results)
    assert n >= 7  # eras pay the first mover
