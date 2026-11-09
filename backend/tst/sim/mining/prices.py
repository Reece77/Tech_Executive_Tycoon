"""The one place M19 reads M17's prices (formulas.md 33): a commodity's spot price in dollars a
tonne of product, and a company's use of it in tonnes."""

from __future__ import annotations

from tst.sim.commodities import commodity
from tst.sim.data_models import Balance, GameData
from tst.sim.state import GameState

KG_PER_T = 1000.0  # tunable-exempt: unit conversion


def per_t(volume_unit: str) -> float:
    """Volume units a tonne (a kilogram good: 1,000)."""
    return KG_PER_T if volume_unit == "kg" else 1.0


def spot_usd_t(state: GameState, key: str, data: GameData, balance: Balance) -> float:
    """This month's spot price in dollars a tonne (M17's price in the good's unit x dollars a
    volume unit x volume units a tonne)."""
    assert data.commodities is not None
    good = data.commodities.good(key)
    p = commodity.price(state, key, state.turn, data, balance)
    return p * good.usd_per_unit * per_t(good.volume_unit)


def long_run_usd_t(state: GameState, key: str, data: GameData, balance: Balance) -> float:
    assert data.commodities is not None
    d = commodity.deck(state, key, data, balance)
    return d.long_run_usd * per_t(d.volume_unit)


def index_now(state: GameState, key: str, data: GameData) -> float:
    return commodity.index_now(state, key, data)


def use_t(volume: float, key: str, data: GameData) -> float:
    """A company's use in the good's volume units, in tonnes."""
    assert data.commodities is not None
    return volume / per_t(data.commodities.good(key).volume_unit)
