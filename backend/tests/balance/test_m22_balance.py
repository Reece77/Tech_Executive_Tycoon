"""docs/formulas.md 39.4 targets (M22), nightly; tools/m22_targets.py prints the same. Values
recorded in docs/balance-targets.md (M22) and the M22 brief. Target 7 also has a fast test
(tests/unit/test_m22_domestic.py)."""

from __future__ import annotations

import os

import pytest

from tst.balance import m22


@pytest.mark.nightly
def test_39_4_targets() -> None:
    r = m22.run(m22.SEEDS, os.cpu_count() or 1)
    print(m22.report(r))
    checked, misses, follows = r.t1
    assert misses == 0 and follows  # target 1
    assert all(0.15 <= x.loss <= 0.30 for x in r.t2)  # target 2
    assert all(0.05 <= x.loss_variant <= 0.15 for x in r.t2)
    assert all(0.30 <= p <= 0.80 for p in r.t3)  # target 3
    lo, hi = r.t4
    assert hi >= 1.2 * lo  # target 4
    assert all(0.08 <= v <= 0.20 for y, v in r.t5 if y >= 2019)  # target 5
    assert 7 <= sum(1 for _, e, d in r.t6 if e and d) <= 10  # target 6
    assert r.t7  # target 7
