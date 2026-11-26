"""M54's balance targets and guards (docs/formulas.md 64.6), printed by tools/m54_targets.py.

Target 1's currency guard (sub-task 2): a company that sells and spends only in North America
plays exactly as before currencies existed. `na_only_digests` plays the `steady` script (one
North American product, no regions) on a seed with the data as loaded and with `fx` removed (every
index 1, nothing translated), digesting each month (M30's canonical digest) the full state and
ledger balances to December 2025, and from January 2026 the player company's own state (its
company record, products, segments and ledger balances): from then rivals' regional lines
translate (ADR-0025 point 4) and the indexes walk, so the world around it moves by design, while
the North American company itself must not (M54 decision 6).
"""

from __future__ import annotations

import hashlib
from functools import cache
from pathlib import Path
from typing import Final

from tst.balance.game import Game, start_game
from tst.balance.m30 import Digester, month_digest
from tst.balance.strategies import STRATEGIES
from tst.loader import LoadedData, load_all

DATA: Final = Path(__file__).resolve().parents[2] / "data"
NA_SEEDS: Final = (1, 2, 3)
NA_TURNS: Final = 240  # January 2010 to December 2029: history and four seeded years
WORLD_TURNS: Final = 192  # the full state is compared to December 2025


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
        if game.state.turn <= WORLD_TURNS:
            out.append(month_digest(digester, game))
        else:
            out.append(_player_digest(digester, game))
    return out


def _player_digest(digester: Digester, game: Game) -> str:
    s = game.state
    pid = s.player.id
    products = tuple(p for p in s.products if p.company_id == pid)
    segments = tuple(x for p in products for x in s.segments_of(p.id))
    regional = tuple(x for p in products for x in s.regional_segments_of(p.id))
    books = tuple(sorted((a, v) for (c, a), v in game.balances.items() if c == pid))
    out = digester.digest((s.player, products, segments, regional, books))
    digester.next_month()
    return hashlib.sha256(out).hexdigest()[:16]
