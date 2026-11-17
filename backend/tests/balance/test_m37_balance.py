"""docs/formulas.md 52.5 targets (M37), nightly; tools/m37_targets.py prints the same. Values
are recorded in the M37 brief ("Decisions made").

Target 1 (nothing moves before 2040) replays M30's nine state-cache runs to December 2039 with
dynasty mode off and on, M37's fields left out of the digest, against the digests recorded
before M37 (tests/fixtures/m37_pre_2040_hashes.json). Targets 2-4 play ten dynasty games with a
family to December 2069. Target 5 (turn time and save size at 2069) is the weekly-m37 job's."""

from __future__ import annotations

import os

import pytest

from tst.balance import m37

JOBS = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))


@pytest.mark.nightly
@pytest.mark.parametrize("dynasty", [False, True], ids=["standard", "dynasty"])
def test_52_5_target_1_nothing_moves_before_2040(dynasty: bool) -> None:
    runs = m37.all_pre_2040(JOBS, (dynasty,))
    diff = {k: v for k, v in m37.compare(runs, m37.legacy()).items() if v is not None}
    assert diff == {}


@pytest.mark.nightly
def test_52_5_targets_2_to_4() -> None:
    results = m37.run_all(JOBS)
    print(m37.report(results))
    x = m37.readings(results)
    n = len(results)
    assert x.eras_median >= 4  # target 2
    assert x.rivals_ok_seeds >= 0.9 * n, x.thin  # target 2
    assert x.commodity_ok, x.excursions  # target 2
    assert x.gaps_lengthen and x.cost_ratio_min >= 0.5  # target 3
    assert x.succession_seeds >= 0.9 * n  # target 4


@pytest.mark.nightly
def test_a_short_dynasty_run_repeats() -> None:
    """The same seed continues the same way (sub-task 3's seeded test): two dynasty runs of a
    family game into 2040 on the same seed give the same digests."""
    first = m37.dynasty_digests(4, 366)
    assert first == m37.dynasty_digests(4, 366)
