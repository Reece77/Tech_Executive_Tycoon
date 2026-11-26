"""Media's place in the turn (docs/formulas.md 65).

- **New game** (`new_game`): the media markets' demand and history for the first month, and each
  media incumbent's opening capital.
- **Phase 5** before the markets (`open_month`): the history's dated openings (M43r) and the ad
  market's prices for ad-funded lines; (`with_effects`): catalogue engagement, ad tiers, network
  effects, formats and moderation; after the markets (`after_sales`): titles' production, release,
  revenue and amortisation, ad revenue, music payouts, licences, moderation, live service, leads'
  deals, laws' deadlines.
- **Phase 9** (`demand_month`): growth draws, demand, seeded eras, generations, strikes and laws,
  the lead pool, the ad market's month, rivals' formats, service months, then the history's pin.

A save without the media markets (made before M55) does nothing here, and a company without media
plays exactly as before (65.8 target 1).
"""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.media import demand, history
from tst.sim.media.data import enabled, is_media_rival
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
    cash = balance.media.rival_cash_cents
    for company in state.rivals():
        if cash > 0 and is_media_rival(company, data):
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=company.id,
                    memo="Opening capital of the media business",
                    debit=CASH,
                    credit=COMMON_EQUITY,
                    amount=cash,
                )
            )
    return state, tuple(entries)


def open_month(state: GameState, balance: Balance, data: GameData) -> GameState:
    if not enabled(state, balance, data):
        return state
    return history.pin(state, balance, data, openings_only=True)


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
    logs: list[LogItem] = []
    state = demand.draw_growth(state, rng, balance, data)
    state = demand.set_demand(state, balance, data)
    return history.pin(state, balance, data), logs
