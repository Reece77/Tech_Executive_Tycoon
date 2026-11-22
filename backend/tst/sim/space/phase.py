"""Space's place in the turn (docs/formulas.md 56).

- **New game** (`new_game`): the space markets' history for January 2010 and every space
  incumbent's opening capital.
- **Phase 5** before the markets (`open_month`): the history's dated openings (M43r);
  (`with_effects`): the player's space lines' gates (designs and
  groundings, coverage and licences, capacity and congestion, D2D, EO); after the markets
  (`after_sales`): customer launches fly, terminals and carriers' shares, constellations' months
  (building, own launches, failures, retirements, coverage, books), lost-satellite events,
  licence decisions.
- **Phase 9** (`demand_month`): the debris rule and rivals' growth, broadband subscribers trimmed
  to capacity, then the history's pin.

A save without the space markets (made before M40) does nothing here, and a company without
space plays exactly as before (56.4 target 1).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.platforms.phase import Effects
from tst.sim.rng import RngFactory
from tst.sim.space import constellation, events, flights, history, launch, policy, services
from tst.sim.space.data import enabled, is_space_rival
from tst.sim.state import GameState


def new_game(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    if not enabled(state, balance, data):
        return state, ()
    state = history.pin(state, balance, data)
    entries = []
    cash = balance.space.rival_cash_cents
    for company in state.rivals():
        if cash > 0 and is_space_rival(company, data):
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=company.id,
                    memo="Opening capital of the space business",
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
    return services.effects(base, state, balance, data)


def open_month(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Phase 5, before the markets: lines whose date opens this month get their price (and, in
    the history, their customers) now, not after the month's sales (M43r, finding 11)."""
    if not enabled(state, balance, data):
        return state
    return history.pin(state, balance, data, openings_only=True)


def after_sales(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    flows: Mapping[tuple[int, str], object],
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not enabled(state, balance, data):
        return state, [], []
    space = state.space
    if not (space.launch_specs or space.constellations or space.licences):
        return state, [], []
    state, customer, logs, used = flights.customer_flights(state, rng, balance)
    state, entries, revenue = services.books(state, flows, balance, data)
    state, more, more_logs, own, lost = constellation.month(
        state, rng, balance, data, revenue, used
    )
    entries += more
    logs += more_logs
    players = {c.id for c in state.companies if c.is_player}
    for cid in lost:
        c = state.space.constellation(cid)
        if c is None or c.company_id not in players:
            continue
        failed = [r for r in own if r.constellation_id == cid and not r.ok]
        sats = sum(r.satellites for r in failed)
        value = sum(
            e.lines[0].amount
            for e in more
            if e.company_id == c.company_id and e.memo == f"Constellation {c.name}: satellites lost"
        )
        vehicle = failed[0].product_id if failed else None
        state = events.queue_failure(state, c, sats, value, vehicle)
    state, licence_logs = policy.licences_month(state, rng, balance, data)
    logs += licence_logs
    flown = (*customer, *own)
    if flown:
        keep = balance.space.history_months
        launches = tuple(r for r in state.space.launches if r.turn > state.turn - keep) + flown
        state = replace(state, space=replace(state.space, launches=launches))
    return state, entries, logs


def demand_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    if not enabled(state, balance, data):
        return state, []
    state, logs = policy.world_month(state, rng, balance, data)
    state = launch.programme_month(state, balance)
    if state.space.constellations:
        state = services.trim_to_capacity(state, balance, data)
    return history.pin(state, balance, data), logs
