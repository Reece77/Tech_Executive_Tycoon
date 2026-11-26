"""M54's balance targets and guards (docs/formulas.md 64.6), printed by tools/m54_targets.py.

Target 1's currency guard (sub-task 2): a company that sells and spends only in North America
plays exactly as before currencies existed. `na_only_digests` plays the `steady` script (one
North American product, no regions) on a seed with the data as loaded and with `fx` removed (every
index 1, nothing translated), digesting the full state and ledger balances each month (M30's
canonical digest); the two runs must agree month by month.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Final

from tst.balance.game import start_game
from tst.balance.m30 import Digester, month_digest
from tst.balance.strategies import STRATEGIES
from tst.loader import LoadedData, load_all

DATA: Final = Path(__file__).resolve().parents[2] / "data"
NA_SEEDS: Final = (1, 2, 3)
NA_TURNS: Final = 240  # January 2010 to December 2029: history and four seeded years


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


@cache
def without_fx() -> LoadedData:
    base = loaded()
    from dataclasses import replace

    return replace(base, game_data=base.game_data.model_copy(update={"fx": None}))


def na_only_digests(seed: int, turns: int = NA_TURNS, *, fx: bool = True) -> list[str]:
    """The steady script's month digests on a seed, with or without currencies."""
    data = loaded() if fx else without_fx()
    game = start_game(data, seed)
    script = STRATEGIES["steady"]
    digester = Digester()
    out: list[str] = []
    while game.state.turn < turns and not game.state.ended:
        script(game)
        game.turn()
        out.append(month_digest(digester, game))
    return out
