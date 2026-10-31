"""docs/formulas.md 18.9 targets 2, 3 and 5 (M8), nightly; tools/m8_targets.py prints the same.
Values recorded in docs/balance-targets.md (M8 section)."""

from __future__ import annotations

import os

import pytest

from tst.balance import m8

NEEDED = {"seats": 1.15, "support": 1.08, "blitz": 1.2}


@pytest.mark.nightly
@pytest.mark.parametrize("arm", list(NEEDED))
def test_m8_target(arm: str) -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    results = m8.run(arm, m8.SEEDS, jobs)
    value = m8.ratio(results)
    print(f"18.9 {arm}: {value:.3f} (needs >= {NEEDED[arm]})")
    assert value >= NEEDED[arm]
