"""M52's 66.4 target 4 on the CI runner: from M45's dynasty game continued in sandbox to December
2100 (tools/m52_save.py), Reece's rule since M60 (tests/calibration.py MONTH_S): the median and
the worst of ten months under 1,000 ms runner-adjusted. Runs only where TST_M52_SAVE names the
save; it copies the save and never changes it."""

from __future__ import annotations

import os
import shutil
import statistics
import time
import warnings
from pathlib import Path

import pytest

from tests.calibration import MONTH_S, adjusted, calibrate, runner_note
from tests.helpers import answer_critical
from tests.integration.test_product_perf import TurnTime
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
    mid, top = adjusted(median, workload), adjusted(worst, workload)
    report = (
        f"M52: from {state.turn} ({len(state.companies)} companies) a 2101 month "
        f"{median * 1000:.0f} ms median, {worst * 1000:.0f} ms at most "
        f"({[round(m * 1000) for m in months]}); {runner_note(median, workload)}; guard: "
        f"adjusted median {mid * 1000:.0f} ms and worst {top * 1000:.0f} ms against "
        f"{MONTH_S * 1000:.0f} ms"
    )
    print(report)
    warnings.warn(TurnTime(report), stacklevel=1)
    assert mid < MONTH_S, report
    assert top < MONTH_S, report
