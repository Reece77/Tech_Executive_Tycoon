"""M52's 66.4 target 4 on the CI runner: from M45's dynasty game continued in sandbox to December
2100 (tools/m52_save.py), a late month within the dynasty guard: the median of ten months
runner-adjusted (tests/calibration.py, as M37's and M30's guards) within 550 ms, or within its
known-miss bound (Reece, 2026-11-26). Runs only where TST_M52_SAVE names the save; it copies the
save and never changes it."""

from __future__ import annotations

import os
import shutil
import statistics
import time
import warnings
from pathlib import Path

import pytest

from tests.calibration import REFERENCE_S, calibrate, runner_note
from tests.helpers import answer_critical
from tests.integration.test_product_perf import TurnTime
from tst.balance.known_misses import Reading, known_miss, verdict
from tst.db import migrate
from tst.db.repository import load_state, open_session, run_turn
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn

pytestmark = [
    pytest.mark.timing,
    pytest.mark.weekly,
    pytest.mark.skipif(
        not os.environ.get("TST_M52_SAVE"), reason="needs TST_M52_SAVE (tools/m52_save.py)"
    ),
]

MEDIAN_S = 0.55  # 66.4 target 4: the dynasty guard, runner-adjusted
TIMING = "M52.2100_month"  # its known-miss target (tst/balance/known_misses.py)
WARM_UP = 2
MONTHS = 10


def test_a_2100_month(tmp_path: Path, loaded: LoadedData) -> None:
    source = Path(os.environ["TST_M52_SAVE"])
    path = tmp_path / source.name
    shutil.copy(source, path)
    migrate.ensure_current(path)
    with open_session(path) as session:
        state = load_state(session)
    assert state.turn >= ym_to_turn(2100, 12) and not state.ended, state.turn
    assert state.mode is not None and state.mode.length == "endless"
    for _ in range(WARM_UP):
        answer_critical(path, loaded)
        run_turn(path, loaded)
    months = []
    for _ in range(MONTHS):
        answer_critical(path, loaded)
        start = time.perf_counter()
        run_turn(path, loaded)
        months.append(time.perf_counter() - start)
    median, worst = statistics.median(months), max(months)
    workload = calibrate()
    ratio = workload / REFERENCE_S
    adjusted = median / ratio
    report = (
        f"M52: from {state.turn} ({len(state.companies)} companies) a 2101 month "
        f"{median * 1000:.0f} ms median, {worst * 1000:.0f} ms at most "
        f"({[round(m * 1000) for m in months]}); {runner_note(median, workload)}; guard: "
        f"adjusted median {adjusted * 1000:.0f} ms against {MEDIAN_S * 1000:.0f} ms"
    )
    print(report)
    warnings.warn(TurnTime(report), stacklevel=1)
    # Reece (2026-11-26): a known miss owned by v6 performance within its bound, as M37's 2069
    # month; the raw 1.0 s worst-month check is not applied at 2100
    reading = Reading(TIMING, adjusted <= MEDIAN_S, adjusted, report)
    assert verdict(reading) != "fail", report
    if verdict(reading) == "known":
        pytest.xfail(f"KNOWN MISS ({known_miss(TIMING).owner}): {report}")  # type: ignore[union-attr]
