"""M14 sub-task 5's turn-time check: integrating the largest incumbent (Apple, about 3,400
pool staff) keeps test_product_perf's budget, under 1 s a turn as the median of three timed
blocks after a warm-up (the same method and limit)."""

from __future__ import annotations

import statistics
import time
import warnings
from pathlib import Path

from tests.helpers import fund_save, move_save_directors, play_turn
from tests.integration.test_product_perf import LIMIT_S, TurnTime
from tst.db.repository import (
    create_save,
    load_state,
    open_session,
    read_session,
    read_state,
    run_action,
)
from tst.loader import LoadedData
from tst.sim.mna.deals import BidForCompany

TURNS = 30
WARM_UP = 3
BLOCKS = 3


def test_integrating_the_largest_incumbent_keeps_the_turn_budget(
    tmp_path: Path, loaded: LoadedData
) -> None:
    path = create_save(
        "mnaperf", 3, "funded_spinout", company_name="Perf Co", data=loaded, save_dir=tmp_path
    )
    move_save_directors(path)
    fund_save(path, 10**15)  # timing, not solvency
    with open_session(path) as session:
        state = load_state(session)
    apple = next(c.id for c in state.companies if c.name == "Apple")
    founder = state.founder_of(1)
    assert founder is not None
    play_turn(path, loaded)  # a month of history for its value
    from tst.api.mna_views import mna_out
    from tst.db.repository import current_balances

    with read_session(path) as session:
        state = read_state(session)
        out = mna_out(state, current_balances(session, state.turn), loaded)
    cap = next(t for t in out.targets if t.company_id == apple).market_cap_cents
    assert cap is not None
    run_action(path, loaded, BidForCompany(founder.id, apple, cap * 3))
    play_turn(path, loaded)
    with open_session(path) as session:
        state = load_state(session)
    (acq,) = state.acquisitions
    assert acq.mode == "integrate" and not state.company(apple).alive
    assert len(state.staff(1)) > acq.key_people

    for _ in range(WARM_UP):
        play_turn(path, loaded)
    size = (TURNS - WARM_UP) // BLOCKS
    blocks = []
    for _ in range(BLOCKS):
        start = time.perf_counter()
        for _ in range(size):
            play_turn(path, loaded)
        blocks.append((time.perf_counter() - start) / size)
    per_turn = statistics.median(blocks)
    report = (
        f"after integrating Apple: median {per_turn * 1000:.0f} ms per turn of blocks "
        f"{[round(b * 1000) for b in blocks]} ms; staff {len(state.staff(1))}, kept "
        f"{acq.pool_kept}, let go {acq.let_go}"
    )
    print(report)
    warnings.warn(TurnTime(report), stacklevel=1)
    assert per_turn < LIMIT_S, report
