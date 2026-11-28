"""The finance markets' demand (docs/formulas.md 64.1-64.3).

**Addressable customers** for a region and segment, each month (phase 9, and at a new game), read
at the month's fractional year to December 2025 (then December 2025's, grown):

    bank_consumer  D = adults with an account (millions) x 10^6 x finserv.scale
    bank_business  D = the same x business_per_consumer
    pay_merchants  D = card volume x (1 - rails' share) / a merchant's volume x scale
    pay_networks   D = card volume x (1 - rails' share) / a network unit x scale
    ins_<line>     D = the line's world premiums x the region's share / (12 x a policy's premium x
                       the region's price index) x scale

From `finserv.start` accounts, policies and card volume grow from December 2025's by rates drawn
each January (stream finserv (4, region index, year); accounts and policies within
`finserv.growth_after`, card volume within `payments.growth_after[region]`; hidden), compounded
monthly; rails' share gains `payments.rail_growth_after` a year up to `rail_cap`. These markets have
no growth rate of their own, so M43a's saturation leaves them to this (saturation.grows).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim import dmath
from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.finserv import draws
from tst.sim.finserv.config import series_at
from tst.sim.finserv.data import (
    BILLION,
    LAST_YEAR,
    MILLION,
    MONTHS,
    file,
    history_year,
    region_index,
)
from tst.sim.products.models import MarketSegment
from tst.sim.rng import RngFactory, text_key
from tst.sim.state import GameState, with_all_markets

ACCOUNTS: Final = 0  # growth kinds (the world's growth rows)
POLICIES: Final = 1
VOLUME: Final = 2
CENTS: Final = 100  # tunable-exempt: cents a dollar
GROWTH_KEY: Final = 4  # tunable-exempt: ADR-0013's key, finserv (4, region index, year)


def growth_factor(
    state: GameState, region: str, kind: int, balance: Balance, data: GameData
) -> float:
    """Now over December 2025: 1 before `finserv.start`, then the drawn yearly rates compounded
    month by month (a whole year at a time: (1 + r) a full year, (1 + r) ** (m / 12) this one)."""
    start = balance.finserv.start_turn
    if state.turn < start:
        return 1.0
    ri = region_index(region, data)
    first, _ = turn_to_ym(start)
    year, month = turn_to_ym(state.turn)
    out = 1.0
    for y in range(first, year + 1):
        rate = state.finserv.world.rate(y, ri, kind) or 0.0
        months = month if y == year else MONTHS
        out *= rate_power(rate, months)
    return out


def rate_power(rate: float, months: int) -> float:
    """(1 + rate) ** (months / 12), exactly 1 + rate for a whole year."""
    if months == MONTHS:
        return 1.0 + rate
    return float(dmath.pow(1.0 + rate, months / MONTHS))


def rails_share(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """Real-time rails' share of the region's card and digital volume this month (64.2)."""
    pb = balance.finserv.payments
    out = 0.0
    for rail in file(data).payments.rails:
        if rail.region != region or state.turn < rail.turn:
            continue
        year = history_year(state.turn, balance)
        share = rail.share_at(year)
        if state.turn >= balance.finserv.start_turn:
            years = (state.turn - balance.finserv.start_turn + 1) / MONTHS
            share = min(pb.rail_cap, share + pb.rail_growth_after * years)
        out = max(out, share)
    return out


def card_volume_dollars(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """The region's card volume a year (real dollars, not scaled), before rails."""
    pts = file(data).payments.volume_bn[region]
    year = history_year(state.turn, balance)
    return series_at(pts, year) * BILLION * growth_factor(state, region, VOLUME, balance, data)


def network_volume_dollars(
    state: GameState, region: str, balance: Balance, data: GameData
) -> float:
    """The region's card-network volume a year: card volume less the rails' share."""
    return card_volume_dollars(state, region, balance, data) * (
        1.0 - rails_share(state, region, balance, data)
    )


def addressable(
    state: GameState, region: str, category: str, segment: str, balance: Balance, data: GameData
) -> float:
    fb = balance.finserv
    f = file(data)
    year = history_year(state.turn, balance)
    if category == fb.banking_category:
        accounts = series_at(f.banking.accounts[region], year) * MILLION * fb.scale
        accounts *= growth_factor(state, region, ACCOUNTS, balance, data)
        return accounts * (f.banking.business_per_consumer if segment == "bank_business" else 1.0)
    if category == fb.payments_category:
        volume = network_volume_dollars(state, region, balance, data)
        # money-exact: ratio (a count of merchants or network units: volume over a unit's)
        unit = (
            f.payments.network_unit_cents
            if segment == "pay_networks"
            else f.payments.volume_per_merchant_cents
        ) / CENTS
        return volume / unit * fb.scale
    line = segment.removeprefix("ins_")
    premiums = series_at(f.insurance.premiums_bn[line], year) * BILLION * CENTS
    premiums *= f.insurance.region_share[region] * growth_factor(
        state, region, POLICIES, balance, data
    )
    index = data.region_market(region).price_index
    # money-exact: ratio (a count of policies: premiums over a policy's)
    return premiums / (MONTHS * f.insurance.premium_2010_cents[line] * index) * fb.scale


def set_demand(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Every finance market's addressable customers this month (module docstring)."""
    cats = balance.finserv.categories
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
    """Each January from `finserv.start`: every region's growth for the year by kind (stream
    finserv (4, region key, year); hidden)."""
    fb = balance.finserv
    year, month = turn_to_ym(state.turn)
    if state.turn < fb.start_turn or month != 1:
        return state
    world = state.finserv.world
    rows = list(world.growth)
    for region in data.region_keys:
        ri = region_index(region, data)
        if world.rate(year, ri, ACCOUNTS) is not None:
            continue
        g = draws.gen(rng, state.turn, GROWTH_KEY, text_key(region), year)
        lo, hi = fb.growth_after.lo, fb.growth_after.hi
        v = fb.payments.growth_after[region]
        rows.append((year, ri, ACCOUNTS, float(lo + (hi - lo) * g.random())))
        rows.append((year, ri, POLICIES, float(lo + (hi - lo) * g.random())))
        rows.append((year, ri, VOLUME, float(v.lo + (v.hi - v.lo) * g.random())))
    world = replace(world, growth=tuple(rows))
    return replace(state, finserv=replace(state.finserv, world=world))


_ = LAST_YEAR
