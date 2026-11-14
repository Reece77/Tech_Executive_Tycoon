"""Reading the living world (docs/formulas.md 41): prices and costs in dollars a unit, a
company's records, and whether the world runs yet. Pure functions of the state and data."""

from __future__ import annotations

from typing import Final

from tst.sim.commodities import commodity
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities import goods
from tst.sim.state import GameState
from tst.sim.world import formulas as wf
from tst.sim.world.config import FOUNDRY_GOOD
from tst.sim.world.models import ChainCompany, WorldFacility, WorldGood

CENTS: Final = 100  # tunable-exempt: cents a dollar
BANDS: Final = 3  # tunable-exempt: the cost curve's published thirds (41.9)


def started(state: GameState) -> bool:
    """The world runs once its chain companies exist (January 2026 onward)."""
    return bool(state.chain_companies)


def world_good(state: GameState, good: str) -> WorldGood | None:
    return next((g for g in state.world_goods if g.good == good), None)


def factor(state: GameState, good: str) -> float:
    """The balance factor this month's price takes (41.2): last month's; 1 without a world."""
    g = world_good(state, good)
    return 1.0 if g is None else g.factor


def chain_record(state: GameState, company_id: int) -> ChainCompany | None:
    return next((c for c in state.chain_companies if c.company_id == company_id), None)


def chain_by_key(state: GameState, key: str) -> ChainCompany | None:
    return next((c for c in state.chain_companies if c.key == key), None)


def facilities_of(state: GameState, company_id: int) -> tuple[WorldFacility, ...]:
    return tuple(f for f in state.world_facilities if f.company_id == company_id)


def foundry_wafer_usd(state: GameState, balance: Balance, data: GameData) -> float:
    """A blended foundry wafer's price this month: the foundry wafer index x world's reference
    x the foundry market's capacity factor (38.3)."""
    from tst.sim.fabs import market  # fabs.market reads this module

    return long_run_usd(state, FOUNDRY_GOOD, balance, data) * market.price_factor(
        state, balance, data
    )


def price_usd(state: GameState, good: str, balance: Balance, data: GameData) -> float:
    """This month's price of a good in dollars a volume unit."""
    if good == FOUNDRY_GOOD:
        return foundry_wafer_usd(state, balance, data)
    return commodity.deck(state, good, data, balance).current_usd


def long_run_usd(state: GameState, good: str, balance: Balance, data: GameData) -> float:
    """The long-run level in dollars a volume unit: M17's 2015-2025 median; a foundry wafer at
    this month's foundry wafer index (wafers get cheaper as nodes age: M12a's index), before
    the foundry market's capacity factor."""
    if good == FOUNDRY_GOOD:
        index = goods.index_now(state, FOUNDRY_GOOD, data) if data.components else 1.0
        return index * balance.world.foundry_wafer_cents / CENTS
    assert data.commodities is not None
    g = data.commodities.good(good)
    history = commodity.history_of(data, good)
    return history.long_run * commodity.price_multiple(good, balance) * g.usd_per_unit


def price_unit(good: str, balance: Balance, data: GameData) -> float:
    """Dollars a volume unit for one price unit (a foundry wafer's price is in dollars)."""
    if good == FOUNDRY_GOOD:
        return 1.0
    assert data.commodities is not None
    return data.commodities.good(good).usd_per_unit


def power_index(state: GameState, region: str, data: GameData) -> float:
    if data.power_history is None:
        return 1.0
    try:
        return commodity.index_now(state, commodity.power_key(region), data)
    except KeyError:
        return 1.0


def cash_cost_usd(state: GameState, f: WorldFacility, balance: Balance, data: GameData) -> float:
    """A facility's cash cost a unit this month (hidden beyond its published range, 41.9)."""
    lr = long_run_usd(state, f.good, balance, data)
    return wf.unit_cash_cost(lr, f.cost, power_index(state, f.region, data), balance.world)


def cost_band(cost: float) -> str:
    """The published range of a cost position (41.9): its third of the cost curve."""
    third = 1 / BANDS
    if cost < third:
        return "low"
    if cost < 2 * third:
        return "middle"
    return "high"
