"""M30's targets on the CI runner (docs/tasks/M30-performance-at-scale.md sub-tasks 2-3): from a
2039 save, a month at most 400 ms at the median and none over 1.0 s (test_product_perf's
budget), and 12 months of Holiday in at most 6 s. The save is V6's (tools/v6_save.py, built by
the weekly workflow's V6 jobs: research_heavy, and full_integrator in weekly-v6-integrator), so
this runs only where TST_V6_SAVE names it; it copies the save and never changes it."""

from __future__ import annotations

import os
import shutil
import statistics
import time
import warnings
from pathlib import Path

import pytest

from tests.calibration import REFERENCE_S, calibrate, runner_note
from tests.helpers import answer_critical, continue_at_end
from tests.integration.test_product_perf import LIMIT_S, TurnTime
from tst import holiday
from tst.db import migrate
from tst.db.repository import load_state, open_session, run_turn
from tst.loader import LoadedData

pytestmark = [
    pytest.mark.timing,
    pytest.mark.weekly,
    pytest.mark.skipif(
        not os.environ.get("TST_V6_SAVE"), reason="needs TST_V6_SAVE (tools/v6_save.py)"
    ),
]

MEDIAN_S = 0.4  # the brief's 2039 median
# The full_integrator save (weekly-v6-integrator) missed it on CI at 439 ms; the PM's ruling
# (2026-11-15) hands the 400 ms to M35 and guards that save at 500 ms meanwhile, so the
# Makefile sets TST_M30_MEDIAN_MS=500 for it. M38 (2026-11-17) set the same for the plain V6
# save. That guard reads the runner-adjusted median: the raw median divided by M35a's runner
# ratio (tests/calibration.py), so a slow runner does not fail it (product manager,
# 2026-11-17). Without the variable a save keeps the raw 400 ms; the 1.0 s worst month and
# test_v6_perf's 1,000 ms stay raw.
MEDIAN_ENV = "TST_M30_MEDIAN_MS"
HOLIDAY_S = 6.0  # the brief's 12 months of Holiday
WARM_UP = 2
MONTHS = 12


def _answer(path: Path, loaded: LoadedData) -> None:
    """What stops a Holiday: blocking events with their first choice, proposals approved (or
    declined when the rules refuse them), as tools/bench.py does."""
    from tst.db.repository import read_session, read_state, run_action
    from tst.sim.actions import ChooseEvent
    from tst.sim.actions.authority import AnswerProposal
    from tst.sim.errors import SimError
    from tst.sim.events.effects import blocking_events

    for _ in range(20):
        with read_session(path) as session:
            state = read_state(session)
        founder = state.founder_of(state.player.id)
        actor = founder.id if founder is not None else 1
        todo: list[object] = [
            ChooseEvent(actor, e.id, e.choices[0].key) for e in blocking_events(state) if e.choices
        ]
        todo += [
            AnswerProposal(actor, p.id, True) for p in state.pending_proposals(state.player.id)
        ]
        if not todo:
            return
        for action in todo:
            try:
                run_action(path, loaded, action)  # type: ignore[arg-type]
            except SimError:
                if isinstance(action, AnswerProposal):
                    run_action(path, loaded, AnswerProposal(actor, action.proposal_id, False))


def _copy(tmp_path: Path, name: str) -> Path:
    source = Path(os.environ["TST_V6_SAVE"])
    folder = tmp_path / name
    folder.mkdir()
    path = folder / source.name
    shutil.copy(source, path)
    migrate.ensure_current(path)  # as the app does when it opens a save
    return path


def test_a_2039_month_and_a_holiday_year(tmp_path: Path, loaded: LoadedData) -> None:
    path = _copy(tmp_path, "turns")
    continue_at_end(path, loaded)  # M37 (52.1): playing on past December 2039
    with open_session(path) as session:
        state = load_state(session)
    assert not state.ended
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
    guard_ms = os.environ.get(MEDIAN_ENV)
    if guard_ms:
        measured, limit = median / ratio, float(guard_ms) / 1000
        guard = f"adjusted median {measured * 1000:.0f} ms against {guard_ms} ms"
    else:
        measured, limit = median, MEDIAN_S
        guard = f"raw median {median * 1000:.0f} ms against {MEDIAN_S * 1000:.0f} ms"

    path = _copy(tmp_path, "holiday")
    continue_at_end(path, loaded)
    played, spent = 0, 0.0
    while played < MONTHS:
        _answer(path, loaded)
        start = time.perf_counter()
        out = holiday.run_holiday(path, loaded, MONTHS - played, "critical")
        spent += time.perf_counter() - start
        played += max(out.months_played, 1)
    report = (
        f"M30: from {state.turn} ({len(state.staff(1))} staff) a month {median * 1000:.0f} ms "
        f"median, {worst * 1000:.0f} ms at most ({[round(m * 1000) for m in months]}); "
        f"12 months of Holiday {spent:.1f} s; {runner_note(median, workload)}; "
        f"guard: {guard} (raw {median * 1000:.0f} ms / runner x{ratio:.2f})"
    )
    print(report)
    warnings.warn(TurnTime(report), stacklevel=1)
    assert measured <= limit, report
    assert worst < LIMIT_S, report
    assert spent <= HOLIDAY_S, report
