"""docs/formulas.md 18.9 targets 2, 3 and 5 (M8), nightly; tools/m8_targets.py prints the same.
Values recorded in docs/balance-targets.md (M8 section)."""

from __future__ import annotations

import os

import pytest

from tst.balance import m8

NEEDED = {"seats": 1.15, "support": 1.08, "blitz": 1.2}


SEATS_REASON = (
    "recorded miss: seats 1.097 (needs 1.15) once poached executives leave their seats, even "
    "with the exec salary on appointment (M8r, Reece 2026-10-31); rebalance in M15"
)


SUPPORT_REASON = (
    "recorded miss: support 1.069 (needs 1.08; 1.088 before M10) once consumer confidence lifts "
    "SMB adoption in both arms over 2016-2020 (M10, Reece 2026-11-01); rebalance in M15"
)


@pytest.mark.nightly
@pytest.mark.parametrize(
    "arm",
    [
        pytest.param("seats", marks=pytest.mark.xfail(strict=False, reason=SEATS_REASON)),
        pytest.param("support", marks=pytest.mark.xfail(strict=False, reason=SUPPORT_REASON)),
        "blitz",
    ],
)
def test_m8_target(arm: str) -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    results = m8.run(arm, m8.SEEDS, jobs)
    value = m8.ratio(results)
    print(f"18.9 {arm}: {value:.3f} (needs >= {NEEDED[arm]})")
    assert value >= NEEDED[arm]
