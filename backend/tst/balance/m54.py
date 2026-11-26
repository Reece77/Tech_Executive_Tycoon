"""M54's balance targets and guards (docs/formulas.md 64.6), printed by tools/m54_targets.py.

Target 1's currency guard (sub-task 2): a company that sells and spends only in North America
plays exactly as before currencies existed. `na_only_digests` plays the `steady` script (one
North American product, no regions) on a seed with the data as loaded and with `fx` removed (every
index 1, nothing translated), digesting each month (M30's canonical digest) the full state and
ledger balances to December 2025, and from January 2026 the company's currency footprint (its
translation marks, currency months, forwards, programmes, FX and hedge account balances and the
translation entries posted for it), which must stay empty: from 2026 rivals' regional lines
translate (ADR-0025 point 4) and the indexes walk, so the world around it, and through
competition the company itself, moves by design (seed 3 differs from October 2026), while the
currency system never touches it (M54 decision 6).
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


FX_ACCOUNTS: Final = (
    "1340_fx_hedge_assets",
    "2340_fx_hedge_liabilities",
    "4940_fx_gains",
    "4945_fx_losses",
)
TRANSLATION_MEMO: Final = "Currency translation"


def footprint(game: Game) -> tuple[object, ...]:
    """The player company's currency footprint this month (module docstring): empty for a
    company that sells and spends only in North America."""
    s = game.state
    pid = s.player.id
    mine = {p.id for p in s.products if p.company_id == pid}
    entries = game.last_result.ledger_entries if game.last_result is not None else ()
    return (
        tuple(m for m in s.fx.marks if m.product_id in mine),
        tuple(m for m in s.fx.months if m.company_id == pid),
        tuple(h for h in s.fx.hedges if h.company_id == pid),
        tuple(p for p in s.fx.programmes if p.company_id == pid),
        tuple(v for (c, a), v in game.balances.items() if c == pid and a in FX_ACCOUNTS and v),
        tuple(e for e in entries if e.company_id == pid and e.memo.startswith(TRANSLATION_MEMO)),
    )


def _player_digest(digester: Digester, game: Game) -> str:
    out = digester.digest(footprint(game))
    digester.next_month()
    return hashlib.sha256(out).hexdigest()[:16]
