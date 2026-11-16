"""Vehicles' place in the turn (docs/formulas.md 49).

- **New game** (`new_game`): the vehicles markets' demand for January 2010, the car makers'
  history (customers, prices, launches) and their opening capital.
- **Phase 4** (`production_month`): vehicle plants' yields, then cell plants run (after refining,
  so the group's lithium is on offer).
- **Phase 5** after the markets (`after_sales`): each player line's month, own cells settled,
  software and licences, autonomy incidents, charging networks.
- **Phase 9** (`demand_month`): the EV-share paths, December's approvals and refreshes, the
  markets' demand, then the history's pin.

A save without the vehicles market (made before M38) does nothing here.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.lifecycle import staffing
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_facility
from tst.sim.vehicles import autonomy, cells, charging, demand, draws, rivals, sales

ATTRIBUTE_MAX = 20  # tunable-exempt: the attribute scale
from tst.sim.vehicles.data import enabled


def new_game(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    if not enabled(state, balance, data):
        return state, ()
    state = demand.set_demand(state, balance, data)
    state = demand.pin(state, balance, data)
    entries = []
    for company in state.rivals():
        if rivals.is_car_maker(company, data) and balance.vehicles.rival_cash_cents > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=company.id,
                    memo="Opening capital of the car business",
                    debit=CASH,
                    credit=COMMON_EQUITY,
                    amount=balance.vehicles.rival_cash_cents,
                )
            )
    return state, tuple(entries)


def plant_yields(state: GameState, rng: RngFactory, balance: Balance) -> GameState:
    """A vehicle plant's yield: lo + (hi - lo) x mean manufacturing skill / 20, x (1 + noise),
    stream vehicles (4, facility) (as 26.2's assembly plants)."""
    vb = balance.vehicles
    y = vb.plant.yield_range
    sd = balance.hardware.plant_yield.noise_sd
    for f in state.facilities:
        if f.kind != vb.plant.kind or f.live_capacity(state.turn) <= 0:
            continue
        mean = staffing(state, f, balance).mean_skill
        noise = float(draws.gen(rng, state.turn, draws.PLANT, f.id).normal(0.0, sd))
        value = (y.lo + (y.hi - y.lo) * mean / ATTRIBUTE_MAX) * (1 + noise)
        floor = balance.hardware.plant_yield.bounds.lo
        state = with_facility(state, replace(f, yield_rate=min(y.hi, max(floor, value))))
    return state


def production_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not enabled(state, balance, data):
        return state, [], []
    state = plant_yields(state, rng, balance)
    return cells.run_plants(state, rng, balance, data)


def after_sales(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not enabled(state, balance, data):
        return state, [], []
    state = sales.month_rows(state, balance, data)
    state, entries = cells.settle(state, balance, data)
    state, more = sales.software_month(state, balance, data)
    entries += more
    state, more, logs = autonomy.incidents_month(state, rng, balance, data)
    entries += more
    state, more, more_logs = charging.networks_month(state, balance, data)
    return state, entries + more, logs + more_logs


def demand_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    if not enabled(state, balance, data):
        return state, []
    state = demand.world_month(state, rng, balance, data)
    state, logs = autonomy.december_approvals(state, rng, balance, data)
    state = rivals.december_refresh(state, rng, balance, data)
    state = demand.set_demand(state, balance, data)
    state = demand.pin(state, balance, data)
    return state, logs
