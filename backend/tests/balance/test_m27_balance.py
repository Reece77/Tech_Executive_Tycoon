"""docs/formulas.md 40.10 targets 1-5 (M27a), nightly; tools/m27_targets.py prints the same.
Values recorded in the M27a brief and docs/balance-targets.md."""

from __future__ import annotations

import os

import pytest

from tst.balance import m27


@pytest.mark.nightly
def test_40_10_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    results = m27.run(m27.SEEDS, jobs)
    print(m27.report(results))
    assert len(m27.arm(results, "spread")) >= 7  # enough seeds reach stage 3
    assert m27.T1_LOW <= m27.target_1(results) <= m27.T1_HIGH  # automate everything works
    arr, mistakes = m27.target_2(results)
    assert arr <= m27.T2_BELOW and mistakes >= m27.T2_MISTAKES  # staff matter
    assert m27.target_3(results) <= m27.T3_BELOW  # workload matters
    proposals, other = m27.target_4(results)
    assert proposals <= m27.T4_PROPOSALS and other <= m27.T4_OTHER  # the inbox stays calm
    assert m27.target_5(results) >= m27.T5_UNSPENT  # founder energy
