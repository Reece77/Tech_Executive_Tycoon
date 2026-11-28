"""M60's turn-time guards in `make check-timing` (docs/tasks/M60-v6-performance.md sub-task 4):
a late month of the v6 world, the median of ten months runner-adjusted (tests/calibration.py, as
M30's, M37's and M52's guards):

- January 2069: M37's dynasty game (full_integrator with a family) whose player also runs the
  v6 industries (tools/profile_m60_v6_arm.py: a mobile network, a chartered bank with accounts,
  a line selling in Europe, a streaming line), within 500 ms;
- December 2100: M52's sandbox continuation of that game (tools/m52_save.py), within 550 ms.

The saves take an hour each to build, so `make timing-saves` builds them, CI's `timing-saves`
workflow keeps them in the Actions cache and `check (timing)` restores them (docs/ci.md). A test
runs only where its variable names a save; it copies the save and never changes it."""

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
from tst.db import migrate
from tst.db.repository import load_state, open_session, run_turn
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn

pytestmark = pytest.mark.timing

WARM_UP = 2
MONTHS = 10
SAVES = {  # variable, first turn at least, the runner-adjusted median's budget (s)
    "2069": ("TST_M60_2069_SAVE", ym_to_turn(2069, 1), 0.50),
    "2100": ("TST_M60_2100_SAVE", ym_to_turn(2100, 12), 0.55),
}


def _months(path: Path, loaded: LoadedData) -> list[float]:
    for _ in range(WARM_UP):
        answer_critical(path, loaded)
        run_turn(path, loaded)
    out = []
    for _ in range(MONTHS):
        answer_critical(path, loaded)
        start = time.perf_counter()
        run_turn(path, loaded)
        out.append(time.perf_counter() - start)
    return out


@pytest.mark.parametrize("year", sorted(SAVES))
def test_a_late_v6_month(year: str, tmp_path: Path, loaded: LoadedData) -> None:
    var, first, budget = SAVES[year]
    if not os.environ.get(var):
        pytest.skip(f"needs {var} (make timing-saves)")
    source = Path(os.environ[var])
    path = tmp_path / source.name
    shutil.copy(source, path)
    migrate.ensure_current(path)
    with open_session(path) as session:
        state = load_state(session)
    assert state.turn >= first and not state.ended, state.turn
    months = _months(path, loaded)
    median = statistics.median(months)
    workload = calibrate()
    adjusted = median / (workload / REFERENCE_S)
    report = (
        f"M60 {year}: from {state.turn} ({len(state.companies)} companies) "
        f"{median * 1000:.0f} ms median, {max(months) * 1000:.0f} ms at most "
        f"({[round(m * 1000) for m in months]}); {runner_note(median, workload)}; guard: "
        f"adjusted median {adjusted * 1000:.0f} ms against {budget * 1000:.0f} ms"
    )
    print(report)
    warnings.warn(TurnTime(report), stacklevel=1)
    assert adjusted <= budget, report
