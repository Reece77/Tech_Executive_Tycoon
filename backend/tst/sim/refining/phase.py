"""Refining's place in the turn (docs/formulas.md 36): phase 4 after the facilities' month
(capex, completion, depreciation) and exploration: contracts that ended, curbs and incidents,
then every plant runs and its output goes to the group, contracts or spot; phase 5 after
production, the group's products take what they used (`plants.settle_supply`).

Nothing here runs for a game without refineries, refinery contracts or last month's supply.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import LedgerEntry
from tst.sim.log import LogItem
from tst.sim.refining import events, plants
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def refining_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    if not state.refineries and not state.refining_deals and not state.own_supply:
        return state, (), ()
    state = replace(state, own_supply=())
    state, logs = plants.end_deals(state)
    state, more = events.events_month(state, rng, balance, data)
    logs += more
    state, entries, more = plants.run_plants(state, balance, data)
    logs += more
    state = plants.record_history(state, balance)
    return state, tuple(entries), tuple(logs)


def settle_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry]]:
    if not state.own_supply:
        return state, []
    return plants.settle_supply(state, balance, data)
