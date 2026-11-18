"""Robotics' place in the turn (docs/formulas.md 53).

- **New game** (`new_game`): the robot markets' demand for January 2010, the industrial makers'
  history, and every robot maker's opening capital.
- **Phase 4** (`production_month`): after the plants' yields, each automated plant's saving a unit
  and its yield (the plant hook reads the saving at sale).
- **Phase 5** before the markets (`with_effects`): the player's humanoids' capability points;
  after the markets (`after_sales`): automated plants' months, humanoid licences, robotaxi zones
  (permits, rides, books, incidents).
- **Phase 9** (`demand_month`): installations' growth and humanoid adoption, the actuators'
  learning, rival operators' new cities, the markets' demand, then the history's pin.

A save without the robotics markets (made before M39) does nothing here, and a company without
robots, humanoids or zones plays exactly as before (53.4 target 1).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.platforms.phase import Effects
from tst.sim.rng import RngFactory
from tst.sim.robotics import automation, demand, humanoids, robotaxi
from tst.sim.robotics.data import enabled, is_robot_maker
from tst.sim.state import GameState


def new_game(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    if not enabled(state, balance, data):
        return state, ()
    state = demand.set_demand(state, balance, data)
    state = demand.pin(state, balance, data)
    entries = []
    cash = balance.robotics.rival_cash_cents
    for company in state.rivals():
        if cash > 0 and is_robot_maker(company, data):
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=company.id,
                    memo="Opening capital of the robot business",
                    debit=CASH,
                    credit=COMMON_EQUITY,
                    amount=cash,
                )
            )
    return state, tuple(entries)


def production_month(state: GameState, balance: Balance, data: GameData) -> GameState:
    if not enabled(state, balance, data):
        return state
    return automation.production_month(state, balance, data)


def with_effects(
    base: Effects | None, state: GameState, balance: Balance, data: GameData
) -> Effects | None:
    """The effects so far with the player's humanoids' capability points added."""
    if not enabled(state, balance, data) or (
        not state.humanoid_specs and not _any_humanoid(state, balance)
    ):
        return base
    bonus = humanoids.effects(state, balance, data)
    if not bonus:
        return base
    b = base if base is not None else Effects()
    feature = dict(b.feature_bonus)
    for k, v in bonus.items():
        feature[k] = feature.get(k, 0.0) + v
    return replace(b, feature_bonus=feature)


def _any_humanoid(state: GameState, balance: Balance) -> bool:
    players = {c.id for c in state.companies if c.is_player}
    return any(
        p.category == balance.robotics.humanoid and p.company_id in players for p in state.products
    )


def after_sales(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not enabled(state, balance, data):
        return state, [], []
    state, entries = automation.after_sales(state, balance, data)
    entries += humanoids.licence_entries(state, balance)
    state, more, logs = robotaxi.zones_month(state, rng, balance, data)
    return state, entries + more, logs


def demand_month(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    if not enabled(state, balance, data):
        return state
    state = demand.world_month(state, rng, balance, data)
    state = humanoids.made_month(state, balance, data)
    state = robotaxi.december_rivals(state, rng, balance, data)
    state = demand.set_demand(state, balance, data)
    return demand.pin(state, balance, data)
