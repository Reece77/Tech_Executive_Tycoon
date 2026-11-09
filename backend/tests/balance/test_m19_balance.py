"""docs/formulas.md 35.6 targets (M19), nightly; tools/m19_targets.py prints the same. Values
recorded in docs/balance-targets.md (M19) and the M19 brief. Target 6 is also the golden
snapshots."""

from __future__ import annotations

import os

import pytest

from tst.balance import m19


@pytest.mark.nightly
def test_35_6_targets() -> None:
    r = m19.run_all(tuple(range(1, 11)), os.cpu_count() or 1, tuple(range(11, 41)))
    print(m19.report(r))
    s = m19.summary(r)
    assert 0.10 <= s["median_irr"] <= 0.20 and s["below_5pct"] >= 0.25  # target 1
    assert 1.5 <= s["copper_aisc_median"] <= 3.0  # target 2
    assert s["high_grade_aisc_median"] <= s["copper_aisc_q1"]  # high grade: the bottom quartile
    for key in ("open_pit", "underground", "brine"):  # target 3
        assert 0.001 <= r.accidents[key] <= 0.005
    assert r.accidents["skill15_over_skill8"] <= 0.6
    assert 3 <= s["seeds_hit"] <= 7  # target 4
    assert s["vol_ratio_max"] <= 0.5  # target 5
    assert r.unchanged  # target 6
