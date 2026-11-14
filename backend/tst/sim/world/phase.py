"""The living world's month (docs/formulas.md 41), in phase 7 after deals and integrations.

In order: the world's first month brings its companies into being (41.1); regions' cycles
step (41.6); chain companies run their month and set each good's balance factor (41.1-41.2);
in December they decide capacity (41.2); rival groups' deals, spin-offs and offtakes (41.3);
bids for the player (41.4); China's catch-up (41.5); then World news (41.7).

Before `world.start` (January 2026) this returns its input unchanged: nothing is drawn, posted
or stored, so 2010-2025 play exactly as before M28 (41.8 target 1).
"""

from __future__ import annotations

from collections.abc import Mapping

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import AccountCode, LedgerEntry, apply_entries
from tst.sim.log import LogItem
from tst.sim.money import Cents
from tst.sim.rng import RngFactory
from tst.sim.state import GameState
from tst.sim.world import bids, china, cycles, decide, groups, news, operate, setup
from tst.sim.world import data as wd


def world_month(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    wb = balance.world
    if state.turn < wb.start_turn or not wd.has_world(data):
        return state, [], []
    entries: list[LedgerEntry] = []
    items: list[news.Item] = []
    running = dict(balances)

    def post(more: list[LedgerEntry]) -> None:
        nonlocal running
        entries.extend(more)
        running = dict(apply_entries(running, more))

    state, opening = setup.materialise(state, rng, balance, data)
    post(opening)
    if not state.chain_companies:
        return state, entries, []
    state, moved = cycles.cycles_month(state, rng, balance, data)
    items += moved
    state, e, n = operate.operate(state, balance, data, running)
    post(e)
    items += n
    state, e, n = decide.decide(state, rng, balance, data, running)
    post(e)
    items += n
    state, e, n = groups.groups_month(state, rng, balance, data, running)
    post(e)
    items += n
    state, n = bids.bids_month(state, rng, balance, data, running)
    items += n
    state, e, n = china.china_month(state, balance, data)
    post(e)
    items += n
    state = news.publish(state, items, wb.news_months)
    return state, entries, []
