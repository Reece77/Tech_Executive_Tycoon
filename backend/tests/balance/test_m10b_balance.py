"""docs/formulas.md 23.7 target 1 (M10b), nightly; tools/m10b_targets.py prints the same.
Values recorded in the M10b brief and docs/balance-targets.md."""

from __future__ import annotations

import os

import pytest

from tst.balance import m10b
from tst.balance.known_misses import Reading, known_miss, verdict

CRITICAL_GAP = 6
SPACING = "M10b.T1.spacing"  # closed in M46: critical follow-ups wait for the slot (16.1)


@pytest.mark.nightly
def test_1_critical_events_for_grown_companies() -> None:
    runs = m10b.run(m10b.SEEDS, int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1))))
    for r in runs:
        print(
            f"seed {r.seed:2d}: {r.big_months} months with 20+ staff, {r.big_criticals} critical "
            f"in them; all critical {list(r.criticals)}; shortest gap {r.shortest_gap}"
        )
    value = m10b.per_window(runs)
    print(f"23.7 target 1: {value:.2f} critical events per 18 months with 20+ staff (needs >= 1)")
    assert sum(r.big_months for r in runs) > 0
    assert value >= 1.0
    close = [r.seed for r in runs if r.shortest_gap is not None and r.shortest_gap < CRITICAL_GAP]
    report = f"seeds with a critical gap under {CRITICAL_GAP} months: {close}"
    print(report)
    reading = Reading(SPACING, not close, float(len(close)), report)
    assert verdict(reading) != "fail", report
    if verdict(reading) == "known":
        pytest.xfail(f"KNOWN MISS ({known_miss(SPACING).owner}): {report}")  # type: ignore[union-attr]
