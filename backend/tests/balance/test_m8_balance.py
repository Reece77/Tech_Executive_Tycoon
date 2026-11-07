"""docs/formulas.md 18.9 targets 2, 3 and 5 (M8), nightly; tools/m8_targets.py prints the same.
Values recorded in docs/balance-targets.md (M8 section)."""

from __future__ import annotations

import os

import pytest

from tst.balance import m8

# 18.9 target 5 ("blitz") 1.2 -> 1.14 (product manager, 2026-11-07, M15a): rival fintech
# startups now launch with features (rivals.startup.start_feature_share), so the scripted
# second product meets real competition; main read 1.224, M15a reads 1.145.
NEEDED = {"seats": 1.15, "support": 1.08, "blitz": 1.14}


@pytest.mark.nightly
@pytest.mark.parametrize(
    "arm",
    [
        "seats",
        "support",
        "blitz",
    ],
)
def test_m8_target(arm: str) -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    results = m8.run(arm, m8.SEEDS, jobs)
    value = m8.ratio(results)
    print(f"18.9 {arm}: {value:.3f} (needs >= {NEEDED[arm]})")
    assert value >= NEEDED[arm]
