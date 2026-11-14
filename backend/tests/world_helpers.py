"""A game in the living world's first month without playing 16 years (M28 tests): a new game
moved to January 2026, its world brought into being. Prices fall back to December 2025's (the
state holds no seeded month), which is what the world's first month reads anyway."""

from __future__ import annotations

from dataclasses import replace

from tst.loader import LoadedData
from tst.sim.ledger import LedgerBalances, apply_entries
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import GameState
from tst.sim.world.setup import materialise

WORLD_START = 192  # January 2026


def world_state(
    loaded: LoadedData, seed: int = 1, turn: int = WORLD_START
) -> tuple[GameState, LedgerBalances]:
    scenario = loaded.game_data.scenario("ex_big_tech_founders")
    assert scenario is not None
    state, entries = new_game(
        save_name="world",
        master_seed=seed,
        scenario=scenario,
        difficulty="standard",
        company_name="World Co",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
    )
    state = replace(state, turn=WORLD_START)
    state, opening = materialise(state, RngFactory(seed), loaded.balance, loaded.game_data)
    balances = apply_entries(apply_entries({}, entries), opening)
    return replace(state, turn=turn), balances
