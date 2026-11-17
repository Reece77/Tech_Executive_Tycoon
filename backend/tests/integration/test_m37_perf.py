"""M37's target 5 (docs/formulas.md 52.5) on the CI runner: from a full_integrator dynasty save
with a family at January 2069 (tools/v6_save.py, built by the weekly-m37 job), no month over
M30's 1.0 s budget. The 500 ms median and the 400 MB save are printed and carried to the v5
performance milestone (the brief's decision 19): a 2069 month reads about 6.5 workloads on
CI against 4.9 for a 2039 month, the cost of 60 years of people and segments, not of a dynasty
rule. Runs only where TST_M37_SAVE names the save; it copies the save and never changes it."""

from __future__ import annotations

import os
import shutil
import statistics
import time
import warnings
from pathlib import Path

import pytest

from tests.calibration import runner_note
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

MEDIAN_S = 0.5  # M30's guard (the brief: "under the 500 ms guard on the CI runner")
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
    report = (
        f"M37: from {state.turn} ({len(state.staff(1))} staff) a 2069 month "
        f"{median * 1000:.0f} ms median, {worst * 1000:.0f} ms at most "
        f"({[round(m * 1000) for m in months]}); save {size / 2**20:.0f} MB; "
        f"{runner_note(median)}"
    )
    print(report)
    warnings.warn(TurnTime(report), stacklevel=1)
    if median > MEDIAN_S:  # carried (decision 19), printed for the v5 performance milestone
        print(f"M37 target 5 carried: median {median * 1000:.0f} ms > {MEDIAN_S * 1000:.0f} ms")
    if size > MAX_BYTES:  # carried too since M41 merged (decision 19): people's records
        print(f"M37 target 5 carried: save {size / 2**20:.0f} MB > {MAX_BYTES / 2**20:.0f} MB")
    assert worst < LIMIT_S, report
