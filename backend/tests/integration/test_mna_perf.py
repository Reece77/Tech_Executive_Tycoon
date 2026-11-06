"""M14 sub-task 5's turn-time checks, under test_product_perf's budget (under 1 s a turn as
the median of three timed blocks after a warm-up, the same method and limit): buying the
largest incumbent (Apple, about 3,400 staff, a brand only since 2026-11-05) and integrating
the largest target within integration.max_staff (250)."""

from __future__ import annotations

import statistics
import time
import warnings
from pathlib import Path

import pytest

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

# Timed alone, without xdist, after the parallel suite: `make check-timing` (M14).
pytestmark = pytest.mark.timing

TURNS = 30
WARM_UP = 3
BLOCKS = 3


def _timed(tmp_path: Path, loaded: LoadedData, pick: str, mode: str) -> None:
    path = create_save(
        "mnaperf", 3, "funded_spinout", company_name="Perf Co", data=loaded, save_dir=tmp_path
    )
    move_save_directors(path)
    fund_save(path, 10**15)  # timing, not solvency
    with open_session(path) as session:
        state = load_state(session)
    from tst.sim.mna.integration import staff_of

    limit = loaded.balance.integration.max_staff
    if pick == "largest":
        apple = next(c.id for c in state.companies if c.name == "Apple")
    else:  # the largest incumbent integration allows
        apple = max(
            (c for c in state.rivals() if staff_of(state, c.id) <= limit),
            key=lambda c: (staff_of(state, c.id), c.id),
        ).id
    founder = state.founder_of(1)
    assert founder is not None
    play_turn(path, loaded)  # a month of history for its value
    from tst.api.mna_views import mna_out
    from tst.db.repository import current_balances

    with read_session(path) as session:
        state = read_state(session)
        out = mna_out(state, current_balances(session, state.turn), loaded)
    t = next(t for t in out.targets if t.company_id == apple)
    cap = t.market_cap_cents or t.value_high_cents
    assert cap is not None
    run_action(path, loaded, BidForCompany(founder.id, apple, cap * 3, mode=mode))  # type: ignore[arg-type]
    play_turn(path, loaded)
    with open_session(path) as session:
        state = load_state(session)
    (acq,) = state.acquisitions
    assert acq.mode == mode
    if mode == "integrate":
        assert not state.company(apple).alive and len(state.staff(1)) > acq.key_people
    else:
        assert state.company(apple).parent_id == 1

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
        f"after buying {state.company(apple).name} ({mode}): median "
        f"{per_turn * 1000:.0f} ms per turn of blocks "
        f"{[round(b * 1000) for b in blocks]} ms; staff {len(state.staff(1))}, kept "
        f"{acq.pool_kept}, let go {acq.let_go}"
    )
    print(report)
    warnings.warn(TurnTime(report), stacklevel=1)
    assert per_turn < LIMIT_S, report


def test_buying_the_largest_incumbent_as_a_brand_keeps_the_turn_budget(
    tmp_path: Path, loaded: LoadedData
) -> None:
    _timed(tmp_path, loaded, "largest", "brand")


def test_integrating_the_largest_allowed_target_keeps_the_turn_budget(
    tmp_path: Path, loaded: LoadedData
) -> None:
    _timed(tmp_path, loaded, "integratable", "integrate")
