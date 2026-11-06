"""M3a and M4a acceptance: 120 turns with 25 staff, 3 products, a board (the funded spinout's
seed director), a SAFE and all incumbents average under 1 s.

M12r: the turns are timed as the median of three blocks after a warm-up, so one noisy
stretch on a shared runner can't decide it (the 1.0 s limit is unchanged; the target is
750 ms on CI). Each turn's read for the launch checks goes through the screens' read path
(`read_session` / `read_state`), which reuses the state the last write published instead of
reloading the whole save; TST_STATE_CACHE_CHECK=1 compares it with a full load."""

from __future__ import annotations

import contextlib
import statistics
import time
import warnings
from pathlib import Path

import pytest

from tests.helpers import FIRST_PRODUCT, fund_save, play_turn
from tests.integration.test_api_org import seed_staff
from tst.db.repository import (
    create_save,
    load_state,
    open_session,
    read_session,
    read_state,
    run_action,
)
from tst.loader import LoadedData
from tst.sim.actions import (
    AssignUnit,
    CreateProduct,
    CreateUnit,
    LaunchProduct,
    MovePerson,
    RaiseSafe,
    SetMarketing,
    SetPrice,
)
from tst.sim.errors import LaunchNotReadyError

# Timed alone, without xdist, after the parallel suite: `make check-timing` (M14).
pytestmark = pytest.mark.timing

STAFF = 24  # employees; 25 with the founder
TURNS = 120
WARM_UP = 6  # turns played before timing starts
BLOCKS = 3  # timed blocks of (TURNS - WARM_UP) / BLOCKS turns; the median decides
LIMIT_S = 1.0  # seconds per turn (M3a); not loosened
PRODUCTS = (
    ("Pipeline", "b2b_saas", {"smb": 4000, "mid_market": 70_000}),
    ("Forge", "dev_tools", {"smb": 2000, "mid_market": 40_000}),
    ("Shield", "cybersecurity", {"smb": 3000, "enterprise": 1_000_000}),
)


def test_product_turn_time_budget(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "prodperf", 3, "funded_spinout", company_name="Perf Co", data=loaded, save_dir=tmp_path
    )
    fund_save(path, 10**11)  # timing, not solvency: keep the long run out of bankruptcy
    seed_staff(path, loaded, STAFF)
    founder = 1
    for name in ("Forge team", "Shield team"):
        run_action(path, loaded, CreateUnit(founder, "team", name))
    for i, pid in enumerate(range(2, 2 + STAFF)):
        if i % 3:
            run_action(path, loaded, MovePerson(founder, pid, i % 3))
    for index, (name, category, prices) in enumerate(PRODUCTS):
        product = FIRST_PRODUCT + index
        run_action(path, loaded, CreateProduct(founder, name, category, tuple(prices)))
        for segment, price in prices.items():
            run_action(path, loaded, SetPrice(founder, product, segment, price))
        run_action(path, loaded, AssignUnit(founder, product, None if index == 0 else index))
        run_action(path, loaded, SetMarketing(founder, product, 500_000))
    run_action(path, loaded, RaiseSafe(founder, 50_000_000, 2_000_000_000))  # M4a
    with open_session(path) as session:
        state = load_state(session)
    assert state.board(1) and state.safes  # M4a: a board and a SAFE
    assert len(state.staff(1)) == STAFF + 1 and len(state.company_products(1)) == len(PRODUCTS)
    incumbent_products = sum(len(c.products) for c in loaded.game_data.incumbents)
    assert len(state.products) == incumbent_products + len(PRODUCTS)

    def turn() -> None:
        with read_session(path) as session:  # as a screen reads it (M12r)
            state = read_state(session)
        for product in state.company_products(1):
            if product.status == "in_development" and product.quality >= 25:
                with contextlib.suppress(LaunchNotReadyError):  # features not there yet
                    run_action(path, loaded, LaunchProduct(founder, product.id))
        play_turn(path, loaded)  # answers a critical event first (M10b: key exits)

    for _ in range(WARM_UP):
        turn()
    size = (TURNS - WARM_UP) // BLOCKS
    blocks = []
    for _ in range(BLOCKS):
        start = time.perf_counter()
        for _ in range(size):
            turn()
        blocks.append((time.perf_counter() - start) / size)
    per_turn = statistics.median(blocks)
    with open_session(path) as session:
        state = load_state(session)
    live = [p.name for p in state.company_products(1) if p.status == "live"]
    report = (
        f"{TURNS} turns: median {per_turn * 1000:.0f} ms per turn of blocks "
        f"{[round(b * 1000) for b in blocks]} ms (read and launch checks included); "
        f"staff {len(state.staff(1))}, products {len(state.products)}, live {live}, "
        f"board confidence {[s.confidence for s in state.board(1)]}"
    )
    print(report)
    warnings.warn(TurnTime(report), stacklevel=1)  # shown in the CI log's warnings summary
    assert per_turn < LIMIT_S, report


class TurnTime(UserWarning):
    """The measured turn time, reported on every run (M12r)."""
