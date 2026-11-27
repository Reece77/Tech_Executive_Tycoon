"""The media markets' demand (docs/formulas.md 65.3-65.5).

**Addressable customers.** For a region, each month (phase 9, and at a new game), read at the
month's year-end point (`end_year_at`) and x `media.scale`:

    streaming  D = paid video subscriptions a region can hold (media.yaml, millions) x 10^6
    music      D = paid music subscriptions a region can hold x 10^6
    games      D = the region's games revenue a year / (12 x the market's reference price x the
                   category's price index there): players at a reference spend a month
    social     D = internet users x multi-homing x 10^6

From `media.start` a region's market grows from December 2025's by a rate drawn each January within
`growth_after[category]` (stream media (3, 2, year, category index, region index); hidden),
compounded monthly. These markets have no growth rate of their own, so M43a's saturation leaves
them to this (saturation.grows).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim import dmath
from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.media import draws
from tst.sim.media.config import BILLION, MILLION, _year_share
from tst.sim.media.data import LAST_YEAR, MONTHS, end_year_at, file, in_history, region_index
from tst.sim.media.models import WorldDraw
from tst.sim.products.models import MarketSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_all_markets
from tst.sim.vehicles.config import interp

GROWTH = "growth"  # tunable-exempt: a WorldDraw kind


def growth_key(category: str, region: str) -> str:
    return f"{category}|{region}"


def growth_factor(
    state: GameState, category: str, region: str, balance: Balance, data: GameData
) -> float:
    """The market now over December 2025's: 1 before `media.start`, then the drawn yearly rates
    compounded month by month."""
    start = balance.media.start_turn
    if state.turn < start:
        return 1.0
    key = growth_key(category, region)
    out = 1.0
    for turn in range(start, state.turn + 1):
        year = turn_to_ym(turn)[0]
        rate = state.media.draw(GROWTH, year, key)
        if rate is None:
            rate = balance.media.growth_after[category].lo
        out *= float(dmath.pow(1.0 + rate, 1.0 / MONTHS))
    return out


def price_index(category: str, region: str, data: GameData) -> float:
    idx = data.category(category).price_index
    return idx.get(region, 1.0) if idx else 1.0


def internet_users(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """A region's internet users (millions, real) now."""
    at = end_year_at(state.turn) if in_history(state.turn, balance) else float(LAST_YEAR)
    base = interp(file(data).internet_users[region], at)
    return base * growth_factor(state, balance.media.social, region, balance, data)


def games_revenue_cents(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """A region's games revenue a year (2010 cents, real) now."""
    f = file(data)
    at = end_year_at(state.turn) if in_history(state.turn, balance) else float(LAST_YEAR)
    world = interp(f.games_market_cents, at) * BILLION
    share = _year_share(f.games_region_share, at, region)
    return world * share * growth_factor(state, balance.media.games, region, balance, data)


def addressable(
    state: GameState, region: str, category: str, balance: Balance, data: GameData
) -> float:
    mb = balance.media
    f = file(data)
    at = end_year_at(state.turn) if in_history(state.turn, balance) else float(LAST_YEAR)
    if category == mb.games:
        ref = data.category(category).markets[0].reference_price_cents
        spend = MONTHS * ref * price_index(category, region, data)  # money-exact: rate
        # money-exact: ratio (players: a year's revenue over a player's spend a year)
        players = games_revenue_cents(state, region, balance, data) / spend
        return players * mb.scale
    if category == mb.social:
        users = internet_users(state, region, balance, data) * interp(f.multi_home, at)
        return users * MILLION * mb.scale
    table = f.streaming_market if category == mb.streaming else f.music_market
    base = interp(table[region], at) * growth_factor(state, category, region, balance, data)
    return base * MILLION * mb.scale


def set_demand(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Every media market's addressable customers this month (module docstring)."""
    cats = balance.media.categories
    home = home_region_of(state, balance, data)
    markets: list[MarketSegment] = []
    changed = False
    for m in state.markets:
        if m.category in cats:
            value = addressable(state, home, m.category, balance, data)
            if value != m.addressable:
                m = replace(m, addressable=value)
                changed = True
        markets.append(m)
    regional = []
    for rm in state.regional_markets:
        if rm.category in cats:
            value = addressable(state, rm.region, rm.category, balance, data)
            if value != rm.addressable:
                rm = replace(rm, addressable=value)
                changed = True
        regional.append(rm)
    if not changed:
        return state
    return with_all_markets(state, markets, regional)


def draw_growth(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """Each January from `media.start`: every media market's growth for the year (stream media
    (3, 2, year, category index, region index); hidden)."""
    mb = balance.media
    year, month = turn_to_ym(state.turn)
    if state.turn < mb.start_turn or month != 1:
        return state
    rows = list(state.media.draws)
    for ci, category in enumerate(mb.categories):
        band = mb.growth_after[category]
        for region in data.region_keys:
            key = growth_key(category, region)
            if state.media.draw(GROWTH, year, key) is not None:
                continue
            ri = region_index(region, data)
            g = draws.gen(rng, state.turn, draws.WORLD, draws.GROWTH, year, ci, ri)
            rows.append(
                WorldDraw(GROWTH, year, key, float(band.lo + (band.hi - band.lo) * g.random()))
            )
    return replace(state, media=replace(state.media, draws=tuple(rows)))
