"""docs/formulas.md 30.7 V6 (M15a): a stage-4 company in 2039 advances at a median of at most
1.0 s a turn (test_product_perf's limit and method: the median of three timed blocks after a
warm-up). The save is built by tools/v6_save.py from a 30-year research_heavy run, which takes
the weekly workflow's time, so this test runs only where TST_V6_SAVE names that save
(.github/workflows/weekly.yml); it copies the save and never changes it."""

from __future__ import annotations

import os
import shutil
import statistics
import time
import warnings
from pathlib import Path

import pytest

from tests.helpers import play_turn
from tests.integration.test_product_perf import LIMIT_S, TurnTime
from tst.db.repository import load_state, open_session
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn

pytestmark = [
    pytest.mark.timing,
    pytest.mark.weekly,
    pytest.mark.skipif(
        not os.environ.get("TST_V6_SAVE"), reason="needs TST_V6_SAVE (tools/v6_save.py)"
    ),
]

WARM_UP = 3
BLOCKS = 3
BLOCK_TURNS = 3


def test_a_2039_stage_4_company_keeps_the_turn_budget(tmp_path: Path, loaded: LoadedData) -> None:
    source = Path(os.environ["TST_V6_SAVE"])
    path = tmp_path / source.name
    shutil.copy(source, path)
    with open_session(path) as session:
        state = load_state(session)
    assert state.turn >= ym_to_turn(2039, 12), state.turn  # December 2039 played
    assert state.player.stage >= 4 and not state.ended
    for _ in range(WARM_UP):
        play_turn(path, loaded)
    blocks = []
    for _ in range(BLOCKS):
        start = time.perf_counter()
        for _ in range(BLOCK_TURNS):
            play_turn(path, loaded)
        blocks.append((time.perf_counter() - start) / BLOCK_TURNS)
    per_turn = statistics.median(blocks)
    report = (
        f"V6: a stage-{state.player.stage} company in {state.turn // 12 + 2010} with "
        f"{len(state.staff(1))} staff: median {per_turn * 1000:.0f} ms per turn of blocks "
        f"{[round(b * 1000) for b in blocks]} ms"
    )
    print(report)
    warnings.warn(TurnTime(report), stacklevel=1)
    assert per_turn < LIMIT_S, report
