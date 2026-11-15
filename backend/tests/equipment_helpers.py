"""M33 tests: a game whose equipment phase runs month by month without the rest of the turn."""

from __future__ import annotations

from dataclasses import replace

from tst.loader import LoadedData
from tst.sim.equipment.phase import equipment_month
from tst.sim.ledger import LedgerBalances, LedgerEntry, apply_entries
from tst.sim.log import LogItem
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import GameState

HISTORY_END = 191  # December 2025
START = 192  # January 2026


def fresh(loaded: LoadedData, seed: int = 1, turn: int = 0) -> tuple[GameState, LedgerBalances]:
    found = loaded.game_data.scenario("ex_big_tech_founders")
    assert found is not None
    state, entries = new_game(
        save_name="equipment",
        master_seed=seed,
        scenario=found,
        difficulty="standard",
        company_name="Litho Co",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
    )
    return replace(state, turn=turn), apply_entries({}, entries)


def run(
    loaded: LoadedData, state: GameState, to_turn: int, seed: int | None = None
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """The equipment phase each month from the state's month to `to_turn` (inclusive)."""
    rng = RngFactory(state.save_meta.master_seed if seed is None else seed)
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    t = state.turn
    while t <= to_turn:
        state = replace(state, turn=t)
        state, more, notes = equipment_month(state, rng, loaded.balance, loaded.game_data)
        entries += more
        logs += notes
        t += 1
    return state, entries, logs
