"""docs/formulas.md 28.9 (M14): the M&A targets on 10 seeds, nightly. Target 1 (nothing
moves without deals) is every earlier balance test plus the golden snapshots."""

from __future__ import annotations

import os

import pytest

from tst.balance import m14


@pytest.mark.nightly
def test_28_9_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    results = m14.run(jobs=jobs)
    print("\n" + m14.report(results))
    private, listed = m14.target_2(results)
    assert private is not None and m14.T2_PRIVATE[0] <= private <= m14.T2_PRIVATE[1]
    assert listed is not None and m14.T2_LISTED[0] <= listed <= m14.T2_LISTED[1]
    integrated, brand = m14.target_3(results)
    assert integrated is not None and m14.T3_INTEGRATED[0] <= integrated <= m14.T3_INTEGRATED[1]
    assert brand is not None and brand <= m14.T3_BRAND_MAX
    scripted, startups = m14.target_4(results)
    lo, hi = m14.T4_SAVINGS
    assert scripted is not None and lo <= scripted <= hi
    ratio = m14.target_5(results)
    assert ratio is not None and m14.T5_RATIO[0] <= ratio <= m14.T5_RATIO[1]
    assert m14.T6_BLOCKED[0] <= m14.target_6(results) <= m14.T6_BLOCKED[1]
    buys = m14.target_7(results)
    assert buys is not None and m14.T7_BUYS[0] <= buys <= m14.T7_BUYS[1]
    del startups
