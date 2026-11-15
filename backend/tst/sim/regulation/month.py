"""Regulation's place in the turn (docs/formulas.md 48), in phase 12 after geopolitics.

From `regulation.start` (January 2026): duties take effect (history's designations of in-game
companies among them), then compliance costs, December designations and warnings, stage steps,
new cases, structural warning signs and orders. Before it nothing runs: history's designations,
duties, cases and fines are regulation.yaml's and platforms.yaml's (48.5 target 1)."""

from __future__ import annotations

from collections.abc import Sequence

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import LedgerBalances, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.regulation import cases, designate, duties, structural
from tst.sim.regulation import data as rdata
from tst.sim.regulation.measure import record_turnover, view
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def regulation_month(
    state: GameState,
    rng: RngFactory,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
    month_entries: Sequence[LedgerEntry] = (),
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not rdata.active(state.turn, balance, data) or not state.platforms:
        return state, [], []
    state = record_turnover(state, month_entries, data)
    logs: list[LogItem] = []
    state, more = duties.start_month(state, balance, data)
    logs += more
    entries = duties.compliance_entries(state, balance)
    v = view(state, balance, data)
    state, more = designate.december(state, v, balances, balance, data)
    logs += more
    state, posted, more = cases.stages_month(state, rng, balance, data)
    entries += posted
    logs += more
    state, more = cases.openings(state, rng, v, balance, data)
    logs += more
    state, more = structural.watches_month(state, balance, data)
    logs += more
    state, posted, more = structural.orders_month(state, rng, balance, data)
    entries += posted
    logs += more
    return state, entries, logs
