"""docs/formulas.md 41.8 target 8 (M28): a 2039 turn with the full world costs no more than 1.3x
the same turn without it, and stays inside the turn budget (test_product_perf's 1.0 s).

The world is played from January 2026 to December 2039 in memory (a do-nothing player with
cash, tst.balance.m28_world), so its 14 years of facilities, deals and news are all there. The
same state is then timed with the world (the full data) and without it (the data with no
chain_companies.yaml: the world phase returns at once, as on main before M28), the median of
three blocks after a warm-up each way. Run alone (`make check-timing`)."""

from __future__ import annotations

import copy
import statistics
import time
import warnings
from dataclasses import replace

import pytest

from tests.integration.test_product_perf import LIMIT_S, TurnTime
from tst.balance.game import Game
from tst.balance.m28 import loaded
from tst.balance.m28_world import turn_of, world_game

pytestmark = pytest.mark.timing

RATIO = 1.3  # 41.8 target 8
WARM_UP = 2
BLOCKS = 3
BLOCK_TURNS = 4


def _timed(game: Game) -> float:
    for _ in range(WARM_UP):
        game.turn()
    blocks = []
    for _ in range(BLOCKS):
        start = time.perf_counter()
        for _ in range(BLOCK_TURNS):
            game.turn()
        blocks.append((time.perf_counter() - start) / BLOCK_TURNS)
    return statistics.median(blocks)


def test_a_2039_turn_with_the_full_world() -> None:
    game = world_game(1)
    while game.state.turn < turn_of(2039, 12):
        game.turn()
    assert len(game.state.world_facilities) > 100 and game.state.chain()
    off = copy.copy(game)
    base = loaded()
    off.loaded = replace(
        base, game_data=base.game_data.model_copy(update={"chain_companies": None})
    )
    off.state, off.balances = game.state, dict(game.balances)
    on = copy.copy(game)
    on.state, on.balances = game.state, dict(game.balances)
    with_world = _timed(on)
    without = _timed(off)
    report = (
        f"41.8 T8: a 2039 turn {with_world * 1000:.0f} ms with the world, "
        f"{without * 1000:.0f} ms without ({with_world / without:.2f}x; "
        f"{len(game.state.world_facilities)} facilities)"
    )
    print(report)
    warnings.warn(TurnTime(report), stacklevel=1)
    assert with_world <= RATIO * without, report
    assert with_world < LIMIT_S, report
