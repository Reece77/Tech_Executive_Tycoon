"""Pharma's markets under M43a's ceilings (docs/formulas.md 54.1, 55.4).

The areas are pseudo-categories, so M43a's phase 9 never sees them; the same rule is applied
here. For each area and region a level (1 before `markets.ceiling_start_year`) scales the
indications' data paths (pharma.yaml `market_b`, `growth_after`). Each month from then on the
area's uncapped growth u is applied as `1 + (u - 1) x factor(A, C)`, M43a's saturation:

    A = the area's sales value there a year (every indication's market x the region's share of
        patients x its price index, as demand prices them, x the level), at the game's scale
    C = saturation.ceiling_cents(area category): `markets.ceiling_share.<pharma_area>` x the
        region's GDP path x economy_scale.money

A market already past its ceiling is held, not cut, until the economy catches up (M43a's rule);
a shrinking market shrinks in full. Rivals' seeded approvals after 2025 are sized by the same
headroom over the whole world (`world_factor`), so their revenue cannot compound past it.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.markets import saturation
from tst.sim.pharma import data as pd
from tst.sim.pharma.config import AreaDef
from tst.sim.pharma.models import MarketLevel
from tst.sim.state import GameState


def level(state: GameState, category: str, region: str) -> float:
    for m in state.pharma_markets:
        if m.category == category and m.region == region:
            return m.level
    return 1.0


def _uncapped_cents(
    data: GameData, balance: Balance, area: AreaDef, region: str, turn: int
) -> float:
    """The area's sales value in the region a year, game cents, before any level."""
    share = area.region_share.get(region, 0.0)
    if share <= 0:
        return 0.0
    weights = sum(s * pd.price_index(data, r) for r, s in area.region_share.items())
    part = share * pd.price_index(data, region) / weights
    world_b = sum(
        pd.market_b(data, ind, turn) for ind in pd.file(data).indications if ind.area == area.key
    )
    return world_b * pd.BILLION * pd.CENTS * balance.pharma.scale * part


def value_cents(
    state: GameState, data: GameData, balance: Balance, area: AreaDef, region: str
) -> float:
    """A: the area's sales value in the region this month, with its level."""
    lvl = level(state, area.category, region)
    # money-exact: ratio (a market's size against its ceiling, never booked)
    return _uncapped_cents(data, balance, area, region, state.turn) * lvl


def month(state: GameState, balance: Balance, data: GameData) -> GameState:
    """This month's levels (from `markets.ceiling_start_year`, with M43a's data present)."""
    if not saturation.active(state, balance, data):
        return state
    rows: list[MarketLevel] = []
    for area in pd.file(data).areas:
        for region in data.region_keys:
            before = _uncapped_cents(data, balance, area, region, state.turn - 1)
            now = _uncapped_cents(data, balance, area, region, state.turn)
            lvl = level(state, area.category, region)
            if before > 0 and now > before:
                u = now / before
                ceiling = saturation.ceiling_cents(state, balance, data, area.category, region)
                f = saturation.factor(before * lvl, ceiling)
                lvl *= (1 + (u - 1) * f) / u
            rows.append(MarketLevel(area.category, region, lvl))
    return replace(state, pharma_markets=tuple(rows))


def world_factor(state: GameState, balance: Balance, data: GameData) -> float:
    """The world's pharma headroom, M43a's factor over every area and region (1 before the
    ceilings apply)."""
    if not saturation.active(state, balance, data):
        return 1.0
    a = c = 0.0
    for area in pd.file(data).areas:
        for region in data.region_keys:
            a += value_cents(state, data, balance, area, region)
            c += saturation.ceiling_cents(state, balance, data, area.category, region)
    return saturation.factor(a, c)
