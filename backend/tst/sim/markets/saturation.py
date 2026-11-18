"""Market ceilings and saturation (docs/formulas.md 54.1; M43a).

Each category's addressable market in a region has a ceiling: `markets.ceiling_share` of the
region's GDP (macro_history.yaml's `gdp` to its last year, then `markets.gdp_growth` a year x the
region's cycle multiplier, 41.6), at the game's economy (x `economy_scale.money`), x (1 +
`markets.era_ceiling_lift` for each arrived era that boosts the category). Phase 9 grows a market
at `g x (1 - A / C)` and never past C (tst.sim.products.phases.brand_and_demand).

A, a market's value, is a year of its addressable customers at reference prices: addressable x
p_ref x the region's price index (relative to the home region, as the game sells) x the units a
customer buys a month (unit-sale markets) x 12, plus a medical device's consumables a year.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from itertools import pairwise
from typing import Final

from tst.sim import dmath
from tst.sim.calendar import turn_to_ym, ym_to_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.geo.formulas import price_ratio
from tst.sim.geo.models import RegionalMarket
from tst.sim.products.models import MarketSegment
from tst.sim.state import GameState, derived

MONTHS: Final = 12  # tunable-exempt: calendar
TRILLION_CENTS: Final = 1e14  # tunable-exempt: a trillion dollars in cents

type Key = tuple[str, str]  # (category, region)


def enabled(balance: Balance, data: GameData) -> bool:
    mh = data.macro_history
    return bool(balance.markets.ceiling_share) and mh is not None and bool(mh.gdp)


def active(state: GameState, balance: Balance, data: GameData) -> bool:
    """Ceilings apply from January of `markets.ceiling_start_year` (PM, 2026-11-18: the
    history to 2025 is main's, recalibrated only where 2025 was outside 0.5-2x, 54.3)."""
    start = ym_to_turn(balance.markets.ceiling_start_year, 1)
    return state.turn >= start and enabled(balance, data)


def _listed(table: dict[int, float], year: float) -> float:
    """Geometric interpolation between listed years; flat before the first."""
    years = sorted(table)
    if year <= years[0]:
        return table[years[0]]
    for lo, hi in pairwise(years):
        if lo <= year <= hi:
            w = (year - lo) / (hi - lo)
            return float(table[lo] * dmath.pow(table[hi] / table[lo], w))
    return table[years[-1]]


def gdp_trend(balance: Balance, data: GameData, region: str, turn: int) -> float:
    """A region's GDP in trillions of dollars a year in `turn`'s month, without its cycle: the
    history (a month's value at its year's fraction), then the trend from the last listed year."""
    assert data.macro_history is not None
    table = data.macro_history.gdp[region]
    y, m = turn_to_ym(turn)
    year = y + (m - 1) / MONTHS
    last = max(table)
    if year <= last:
        return _listed(table, year)
    growth = balance.markets.gdp_growth.get(region, 0.0)
    return float(table[last] * dmath.pow(1 + growth, year - last))


def cycle(state: GameState, region: str) -> float:
    """The region's cycle multiplier this month (41.6; 1 before 2026)."""
    for c in state.region_cycles:
        if c.region == region:
            return c.multiplier if c.multiplier > 0 else 1.0
    return 1.0


def eras_lifting(state: GameState, data: GameData, category: str) -> int:
    """Arrived eras with a boost to the category (54.1: an era makes a market bigger)."""
    from tst.sim.research.eras import arrived

    return sum(
        1
        for era, a in arrived(state, data)
        if a.turn <= state.turn and any(b.category == category for b in era.boosts)
    )


def ceiling_cents(
    state: GameState, balance: Balance, data: GameData, category: str, region: str
) -> float:
    """C: cents a year (54.1)."""
    mb = balance.markets
    gdp = gdp_trend(balance, data, region, state.turn) * cycle(state, region)
    lift = 1 + mb.era_ceiling_lift * eras_lifting(state, data, category)
    return mb.ceiling_of(category) * gdp * TRILLION_CENTS * balance.economy_scale.money * lift


def _consumables(data: GameData, category: str) -> float:
    from tst.sim.medical import data as md

    sub = md.subcategory(data, category)
    return float(sub.consumables_cents) if sub is not None else 0.0


def segment_value(data: GameData, category: str, segment: str, region: str, home: str) -> float:
    """Cents a year one addressable customer is worth in a region (module docstring)."""
    from tst.sim.products.formulas import sale_rate

    cat = data.category(category)
    m = cat.market(segment)
    index = 1.0 if region == home else float(price_ratio(region, home, data))
    # money-exact: ratio (a market's size against its ceiling, never booked)
    monthly = m.reference_price_cents * sale_rate(cat, segment)
    if cat.medical:
        monthly += m.units_per_customer * _consumables(data, category)
    return monthly * index * MONTHS


def value_per_customer(
    state: GameState, data: GameData, home: str
) -> dict[tuple[str, str, str], float]:
    """(category, segment, region) -> segment_value, once per state."""
    return derived(
        state,
        ("market_value_per_customer", id(data), home),
        lambda: {
            (cat.key, m.segment, r.key): segment_value(data, cat.key, m.segment, r.key, home)
            for cat in data.categories
            for m in cat.markets
            for r in data.regions
        },
    )


def market_values(
    state: GameState, rows: Iterable[tuple[str, str, str, float]], data: GameData, home: str
) -> dict[Key, float]:
    """A per (category, region) from (category, segment, region, addressable) rows."""
    values = value_per_customer(state, data, home)
    out: dict[Key, float] = {}
    for category, segment, region, addressable in rows:
        k = (category, region)
        out[k] = out.get(k, 0.0) + addressable * values[(category, segment, region)]
    return out


def ceilings(
    state: GameState, balance: Balance, data: GameData, keys: Iterable[Key]
) -> dict[Key, float]:
    """C for each (category, region), once per state."""
    wanted = tuple(sorted(set(keys)))
    return derived(
        state,
        ("market_ceilings", id(data), id(balance), wanted),
        lambda: {k: ceiling_cents(state, balance, data, *k) for k in wanted},
    )


def factor(value: float, ceiling: float) -> float:
    """Saturation: growth x (1 - A / C), between 0 and 1 (54.1)."""
    if ceiling <= 0:
        return 0.0
    return min(1.0, max(0.0, 1.0 - value / ceiling))


def grows(data: GameData, category: str) -> bool:
    """Whether the category's demand grows in phase 9 (has a growth rate): markets whose
    demand data sets each month (vehicles, M38; robots, M39) have none and no ceiling here."""
    cat = data.category(category)
    if category in data.eras.base_growth:
        return True
    return cat.growth > 0 or any(g > 0 for g in (cat.growth_by_year or {}).values())


def clamp[M: MarketSegment, R: RegionalMarket](
    state: GameState,
    data: GameData,
    home: str,
    caps: dict[Key, float],
    before: dict[Key, float],
    markets: list[M],
    regional: list[R],
) -> tuple[list[M], list[R]]:
    """Scale a (category, region)'s segments back where growth (or a cycle) took it past its
    ceiling (54.1: a market can't pass its ceiling). A market already past it (one that came
    out of the history above it in January 2026) is held at its size before this month's
    growth, never cut: it waits for the economy to catch up."""
    rows = [(m.category, m.segment, home, m.addressable) for m in markets]
    rows += [(r.category, r.segment, r.region, r.addressable) for r in regional]
    values = market_values(state, rows, data, home)
    limit = {k: max(c, before.get(k, 0.0)) for k, c in caps.items()}
    over = {k: limit[k] / v for k, v in values.items() if k in limit and v > limit[k]}
    if not over:
        return markets, regional
    out_m = [
        replace(m, addressable=m.addressable * over[(m.category, home)])
        if (m.category, home) in over
        else m
        for m in markets
    ]
    out_r = [
        replace(r, addressable=r.addressable * over[(r.category, r.region)])
        if (r.category, r.region) in over
        else r
        for r in regional
    ]
    return out_m, out_r
