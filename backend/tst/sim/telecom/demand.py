"""The telecom markets' demand (docs/formulas.md 62.1).

**Addressable customers.** For a region and segment, each month (phase 9, and at a new game):

    mobile    D = subscriptions (telecom.yaml, millions) x 10^6 x telecom.scale x mobile_split[seg]
    fixed     D = fixed broadband subscriptions x 10^6 x telecom.scale x fixed_split[seg]
    wholesale D = mobile subscriptions (millions) x wholesale_per_sub x telecom.scale
    equipment D = mobile subscriptions x 10^6 x equipment_sites_per_sub x telecom.scale

read at the month's year-end point (`end_year_at`). From `telecom.start` a region's subscriptions
grow from December 2025's by a rate drawn each January within `growth_after[region]` (stream
telecom (0, year, region index); hidden), compounded monthly: population and adoption; price and
quality act through the segment's outside option, as every market's. These markets have no
growth rate of their own, so M43a's saturation leaves them to this (saturation.grows).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim import dmath
from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.products.models import MarketSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_all_markets
from tst.sim.telecom import draws
from tst.sim.telecom.data import (
    LAST_YEAR,
    MILLION,
    MONTHS,
    end_year_at,
    file,
    in_history,
    region_index,
)


def growth_factor(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """Subscriptions now over December 2025's: 1 before `telecom.start`, then the drawn yearly
    rates compounded month by month."""
    start = balance.telecom.start_turn
    if state.turn < start:
        return 1.0
    ri = region_index(region, data)
    out = 1.0
    for turn in range(start, state.turn + 1):
        year = turn_to_ym(turn)[0]
        rate = state.telecom.world.rate(year, ri)
        if rate is None:
            rate = balance.telecom.growth_after[region].lo
        out *= float(dmath.pow(1.0 + rate, 1.0 / MONTHS))
    return out


def subscriptions(
    state: GameState, region: str, kind: str, balance: Balance, data: GameData
) -> float:
    """A region's subscriptions (real world, millions) of `kind` ("mobile" or "fixed") now."""
    r = file(data).region(region)
    at = end_year_at(state.turn) if in_history(state.turn, balance) else float(LAST_YEAR)
    base = r.mobile_at(at) if kind == "mobile" else r.fixed_at(at)
    return base * growth_factor(state, region, balance, data)


def addressable(
    state: GameState, region: str, category: str, segment: str, balance: Balance, data: GameData
) -> float:
    tb = balance.telecom
    if category == tb.mobile:
        return (
            subscriptions(state, region, "mobile", balance, data)
            * MILLION
            * tb.scale
            * (tb.mobile_split.get(segment, 0.0))
        )
    if category == tb.fixed:
        return (
            subscriptions(state, region, "fixed", balance, data)
            * MILLION
            * tb.scale
            * (tb.fixed_split.get(segment, 0.0))
        )
    mobile = subscriptions(state, region, "mobile", balance, data)
    if category == tb.equipment:
        return mobile * MILLION * tb.equipment_sites_per_sub * tb.scale
    return mobile * tb.wholesale_per_sub * tb.scale


def set_demand(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Every telecom market's addressable customers this month (module docstring)."""
    tb = balance.telecom
    cats = tb.categories
    home = home_region_of(state, balance, data)
    markets: list[MarketSegment] = []
    changed = False
    for m in state.markets:
        if m.category in cats:
            value = addressable(state, home, m.category, m.segment, balance, data)
            if value != m.addressable:
                m = replace(m, addressable=value)
                changed = True
        markets.append(m)
    regional = []
    for rm in state.regional_markets:
        if rm.category in cats:
            value = addressable(state, rm.region, rm.category, rm.segment, balance, data)
            if value != rm.addressable:
                rm = replace(rm, addressable=value)
                changed = True
        regional.append(rm)
    if not changed:
        return state
    return with_all_markets(state, markets, regional)


def draw_growth(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """Each January from `telecom.start`: every region's subscription growth for the year
    (stream telecom (0, 0, year, region index); hidden)."""
    tb = balance.telecom
    year, month = turn_to_ym(state.turn)
    if state.turn < tb.start_turn or month != 1:
        return state
    world = state.telecom.world
    rows = list(world.growth)
    for region in data.region_keys:
        ri = region_index(region, data)
        if world.rate(year, ri) is not None:
            continue
        band = tb.growth_after[region]
        g = draws.gen(rng, state.turn, draws.WORLD, draws.GROWTH, year, ri)
        rows.append((year, ri, float(band.lo + (band.hi - band.lo) * g.random())))
    world = replace(world, growth=tuple(rows))
    return replace(state, telecom=replace(state.telecom, world=world))
