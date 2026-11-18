"""M37's target 5 (docs/formulas.md 52.5) on the CI runner: from a full_integrator dynasty save
with a family at January 2069 (tools/v6_save.py, built by the weekly-m37 job), no month over
M30's 1.0 s budget. M37 printed the 500 ms median and the 400 MB save and carried them to M45
(PM, 2026-11-17; the brief's decision 19); M45 guards both: the median runner-adjusted, as M30's
500 ms guard is (the raw median over M35a's runner ratio, tests/calibration.py), and the save's
size raw. Runs only where TST_M37_SAVE names the save; it copies the save and never changes it."""

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
from tests.integration.test_product_perf import LIMIT_S, TurnTime
from tst.db import migrate
from tst.db.repository import load_state, open_session, run_turn
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn

pytestmark = [
    pytest.mark.timing,
    pytest.mark.weekly,
    pytest.mark.skipif(
        not os.environ.get("TST_M37_SAVE"), reason="needs TST_M37_SAVE (tools/v6_save.py)"
    ),
]

MEDIAN_S = 0.5  # M45's 2069 median, runner-adjusted (M45 brief, sub-task 6)
MAX_BYTES = 400 * 1024 * 1024  # 400 MB
WARM_UP = 2
MONTHS = 10  # March to December 2069


def test_a_2069_month_and_the_save_size(tmp_path: Path, loaded: LoadedData) -> None:
    source = Path(os.environ["TST_M37_SAVE"])
    size = source.stat().st_size
    path = tmp_path / source.name
    shutil.copy(source, path)
    migrate.ensure_current(path)
    with open_session(path) as session:
        state = load_state(session)
    assert state.turn >= ym_to_turn(2069, 1) and not state.ended, state.turn
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
        f"M37: from {state.turn} ({len(state.staff(1))} staff) a 2069 month "
        f"{median * 1000:.0f} ms median, {worst * 1000:.0f} ms at most "
        f"({[round(m * 1000) for m in months]}); save {size / 2**20:.0f} MB; "
        f"{runner_note(median, workload)}; guard: adjusted median {adjusted * 1000:.0f} ms "
        f"against {MEDIAN_S * 1000:.0f} ms (raw {median * 1000:.0f} ms / runner x{ratio:.2f})"
    )
    print(report)
    warnings.warn(TurnTime(report), stacklevel=1)
    assert adjusted <= MEDIAN_S, report
    assert size <= MAX_BYTES, report
    assert worst < LIMIT_S, report
