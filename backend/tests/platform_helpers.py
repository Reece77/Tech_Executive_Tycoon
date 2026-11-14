"""A game at any month without playing to it (M31 tests): a new game moved to `turn`, its
platforms materialised from platforms.yaml."""

from __future__ import annotations

from dataclasses import replace

from tst.loader import LoadedData
from tst.sim.ledger import LedgerBalances, apply_entries
from tst.sim.platforms import data as pdata
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import GameState

HISTORY_END = 191  # December 2025
START = 192  # January 2026


def platform_state(
    loaded: LoadedData, seed: int = 1, turn: int = START, scenario: str = "ex_big_tech_founders"
) -> tuple[GameState, LedgerBalances]:
    found = loaded.game_data.scenario(scenario)
    assert found is not None
    state, entries = new_game(
        save_name="platforms",
        master_seed=seed,
        scenario=found,
        difficulty="standard",
        company_name="Platform Co",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
    )
    state = replace(state, turn=turn)
    state = pdata.materialise(state, loaded.balance, loaded.game_data)
    return state, apply_entries({}, entries)
