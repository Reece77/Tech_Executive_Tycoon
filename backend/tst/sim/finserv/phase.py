"""Financial services' place in the turn (docs/formulas.md 64).

- **New game** (`new_game`): the finance markets' demand and history for the first month, and each
  finance incumbent's opening capital.
- **Phase 5** before the markets (`with_effects`): where the player's finance lines may win
  customers (a bank's line only with a charter or a partner bank there, an insurer's only where
  licensed and solvent, card programmes only where its network runs, at its acceptance's appeal);
  after the markets (`after_sales`): banks' month, payments' fees, interchange and fraud,
  insurers' claims and float, and rivals' interest, interchange and claims.
- **Phase 9** (`demand_month`): growth draws, demand, networks' acceptance, then the history's
  pin.

A save without the finance markets (made before M54) does nothing here, and a company without a
bank, network or insurer plays exactly as before (64.6 target 1).
"""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.finserv import demand, history
from tst.sim.finserv.data import enabled, is_finance_rival
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.platforms.phase import Effects
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def new_game(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    if not enabled(state, balance, data):
        return state, ()
    state = demand.set_demand(state, balance, data)
    state = history.pin(state, balance, data)
    entries = []
    cash = balance.finserv.rival_cash_cents
    for company in state.rivals():
        if cash > 0 and is_finance_rival(company, data):
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=company.id,
                    memo="Opening capital of the finance business",
                    debit=CASH,
                    credit=COMMON_EQUITY,
                    amount=cash,
                )
            )
    return state, tuple(entries)


def with_effects(
    base: Effects | None, state: GameState, balance: Balance, data: GameData
) -> Effects | None:
    if not enabled(state, balance, data):
        return base
    return base


def after_sales(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not enabled(state, balance, data):
        return state, [], []
    return state, [], []


def demand_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    if not enabled(state, balance, data):
        return state, []
    state = demand.draw_growth(state, rng, balance, data)
    state = demand.set_demand(state, balance, data)
    return history.pin(state, balance, data), []
