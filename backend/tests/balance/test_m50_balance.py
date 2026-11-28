"""M50's 60.3 targets 2-3 (nightly; tst.balance.m50), on seeds 1-10: the 2008 crisis is felt
from a January 2008 start and the dated arrivals land on time, each reading within its band.
Target 1 is M50's own determinism and fixture tests; target 4 (V1 from 2008) is reported, as
M50's decision 15 records (its research_heavy wins are V2.wins' known miss). M57r-B (review 10
item 27): these printed and exited 0, with no test."""

from __future__ import annotations

import os

import pytest

from tst.balance import m50


@pytest.mark.nightly
def test_60_3_targets_2_and_3() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    runs = m50.worlds(m50.SEEDS, jobs)
    readings = m50.crisis_readings(runs) + m50.arrival_readings(runs)
    text = m50.table(readings)
    print(text)
    assert readings
    missed = [r for r in readings if r.ok is False]
    assert not missed, text
