"""The power month (docs/formulas.md 46, ADR-0022), in two parts.

**Start of phase 4** (before facilities run): the game-wide draws (46.2), the year's regional
paths after 2025 (46.3-46.4), PPAs that end, the stage-4 plant unlock's one-off notice, grid
queues' connections and held loads (46.3), the month's grid outages (46.5), and plants' capex,
completion, depreciation and forced outages (46.2, 46.5).

**End of phase 6** (after every facility posted its energy at the grid price): the settlement
(tst.sim.power.settle; ADR-0022 3).

Without power.yaml loaded both return their input unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import AccountCode, LedgerEntry, apply_entries
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import Cents
from tst.sim.power import disclosure, outages, paths, plants, ppa, queues, settle
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def _unlocks(state: GameState, balance: Balance) -> tuple[GameState, list[LogItem]]:
    """The stage-4 unlock (46.2): the player's company is told once that it can own plants."""
    done = set(state.power_world.unlocked)
    logs: list[LogItem] = []
    new: list[int] = []
    for c in state.companies:
        if c.is_player and c.id not in done and plants.plants_unlocked(state, c.id, balance):
            new.append(c.id)
            logs.append(inbox_item(state.turn, c.id, "plants_unlocked"))
    if not new:
        return state, logs
    world = replace(state.power_world, unlocked=tuple(sorted({*done, *new})))
    return replace(state, power_world=world), logs


def power_start(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if data.power is None:
        return state, [], []
    logs: list[LogItem] = []
    state = plants.draw_world(state, rng, balance, data)
    state = paths.paths_month(state, rng, balance, data)
    state = ppa.end_month(state)
    state, more = _unlocks(state, balance)
    logs += more
    state, more = queues.queue_month(state, rng, balance, data)
    logs += more
    state, more = outages.outages_month(state, rng, balance, data)
    logs += more
    entries: list[LedgerEntry] = []
    if state.plants:
        state, entries, more = plants.plants_month(state, rng, balance, data)
        logs += more
    return state, entries, logs


def power_end(
    state: GameState,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """The settlement, then (in December, from power.start) the year's disclosure (46.4)."""
    if data.power is None:
        return state, [], []
    state, entries = settle.settle(state, balance, data)
    state, logs = disclosure.disclose(state, balance, data, apply_entries(balances, entries))
    return state, entries, logs
