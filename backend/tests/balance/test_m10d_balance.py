"""M10d (product manager, 2026-11-02): rivals carry the threat. In a 30+ person company the
player loses 0.5-1.5 staff a year to rivals (median of 10 seeds, steady and blitzscale)."""

from __future__ import annotations

import os

import pytest

from tst.balance import m10d

LOSS_BAND = (0.5, 1.5)


@pytest.mark.nightly
def test_staff_lost_to_rivals() -> None:
    runs = m10d.run(m10d.SEEDS, int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1))))
    for name in m10d.STRATEGY_NAMES:
        value = m10d.median_per_year(runs, name)
        seeds = [
            round(r.per_year, 2) for r in runs if r.strategy == name and r.per_year is not None
        ]
        print(f"15.7 target 6, {name}: {value} staff a year to rivals with 30+ staff; {seeds}")
        assert value is not None and LOSS_BAND[0] <= value <= LOSS_BAND[1]
