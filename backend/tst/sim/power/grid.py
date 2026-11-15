"""The grid price (docs/formulas.md 46.2, ADR-0022 1-2): what every metered facility pays a MWh.

    grid price (cents a MWh) = refining.power_cents_per_mwh x multiplier(region)
    multiplier = M17's index (33.5; from 2026 x M28's balance factor for the region's power good)
                 + the carbon pass-through after power.start:
                   pass_through x (carbon now - carbon in 2025) x grid intensity now
                   / the reference price in dollars a MWh

To December 2025 the multiplier is M17's index exactly (the data's prices already include
carbon), so every facility pays what it paid before M32 (46.8 target 1). Every pricing site reads
`multiplier`; nothing else prices energy.
"""

from __future__ import annotations

from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.commodities import power as m17
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.power.config import interp
from tst.sim.power.models import RegionPath
from tst.sim.state import GameState

CENTS: Final = 100  # tunable-exempt: cents a dollar
HISTORY_YEAR: Final = 2025  # tunable-exempt: the data's last year (46.8 target 1)
FLOOR: Final = 0.05  # tunable-exempt: the multiplier never falls below 5% of the index


def year_of(turn: int) -> int:
    return turn_to_ym(turn)[0]


def started(state: GameState, balance: Balance) -> bool:
    return state.turn >= month_to_turn(balance.power.start)


def path(state: GameState, region: str) -> RegionPath | None:
    """The region's seeded path for this year (after 2025), if it has been drawn."""
    year = year_of(state.turn)
    return next((p for p in state.region_paths if p.region == region and p.year == year), None)


def carbon_price(state: GameState, region: str, data: GameData) -> float:
    """$/t (2010 dollars) this month: the data's to 2025, then the seeded path."""
    if data.power is None:
        return 0.0
    p = path(state, region)
    if p is not None:
        return p.carbon
    year = min(year_of(state.turn), HISTORY_YEAR)
    return data.power.region(region).carbon_at(year)


def intensity(state: GameState, region: str, data: GameData) -> float:
    """The grid's tCO2 a MWh this month: the data's (linear by year) to 2025, then the path."""
    if data.power is None:
        return 0.0
    p = path(state, region)
    if p is not None:
        return p.intensity
    pts = data.power.region(region).grid_intensity
    return interp(pts, min(year_of(state.turn), HISTORY_YEAR))


def carbon_uplift(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """The pass-through in dollars a MWh (0 before power.start or without the data)."""
    if data.power is None or not started(state, balance):
        return 0.0
    ref = data.power.region(region).carbon_at(HISTORY_YEAR)
    change = carbon_price(state, region, data) - ref
    return balance.power.carbon.pass_through * change * intensity(state, region, data)


def multiplier(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """The multiple on the reference price a facility in `region` pays this month (module
    docstring)."""
    index = m17.index(state, region, data)
    uplift = carbon_uplift(state, region, balance, data)
    if uplift == 0.0:
        return index
    ref_usd = balance.refining.power_cents_per_mwh / CENTS
    return max(index * FLOOR, index + uplift / ref_usd)


def price_cents(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """The grid price this month, cents a MWh (2010 cents)."""
    return balance.refining.power_cents_per_mwh * multiplier(state, region, balance, data)


def kind_multiplier(
    state: GameState, kind: str, region: str, balance: Balance, data: GameData
) -> float:
    """The multiple on a facility kind's operating cost (33.5): the grid's for metered
    data-centre kinds, 1.0 for kinds whose power sits in their fixed costs."""
    if kind not in balance.power.paid_by:
        return 1.0
    return multiplier(state, region, balance, data)
