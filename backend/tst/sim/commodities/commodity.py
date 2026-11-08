"""Commodity and power goods (docs/formulas.md 33.1, 33.5; ADR-0020 3: one market-good model).

A commodity is a market good whose month is a `GoodMonth` like M12a's components: its `index`
is its price over its 2010-2019 mean (33.1), so 1.0 is "normal". To December 2025 the month is
history (`commodities_history.yaml`, the same on every seed); after it, a seeded path:

- the trend `base` takes a monthly log-price AR(1) step toward the long-run level (the
  2015-2025 median) with monthly persistence `phi ** (1/12)` and sd `vol / sqrt(12)`;
- a shock starts with the kinds' summed monthly chance (an export ban x `concentrated_mult`
  where one country holds over `ban_concentration`) when none has run in the last
  `gap_months` months after the latest ended: the price rises by a drawn share for a drawn
  number of months, spot allocation falls to a drawn level, then the rise fades over as many
  months (M12a's rule);
- `index = base x (1 + the shock's premium)`.

Power is a good by region (`power_<region>`): an index with North America 1.0 in every month;
history to 2025 (`power_history.yaml`), then the same AR(1) toward the region's 2010-2019 mean
without shocks.

Stream `commodity` (id 47): key (0, good_index) for a commodity, drawing in this fixed order
every month after 2025 whether used or not: the AR(1)'s standard normal, then uniforms for the
shock's start, kind, rise, allocation and length; key (1, region_index) for power, one
standard normal. Commodity and power months live in `GameState.supply` after M12a's goods,
sorted by key. Nothing looks ahead: `price` refuses a month after the state's.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from tst.sim.commodities.config import AnnualHistory, CommodityBalance
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import CommodityRuleError
from tst.sim.facilities.goods import shock_premium
from tst.sim.facilities.models import GoodMonth
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

MONTHS_PER_YEAR = 12  # tunable-exempt: calendar
UNIFORMS = 5  # tunable-exempt: start, kind, rise, allocation and length draws
COMMODITY_KEY = 0  # tunable-exempt: stream key family for commodities (0, good_index)
POWER_KEY = 1  # tunable-exempt: stream key family for power (1, region_index)
POWER_PREFIX = "power_"  # tunable-exempt: a power good's key is power_<region>
EXPORT_BAN = "export_ban"  # tunable-exempt: the shock kind that concentration makes likelier


class FutureMonthError(CommodityRuleError):
    """A price for a month after the state's was asked for (33.6 target 1: nothing ahead)."""


def power_key(region: str) -> str:
    return f"{POWER_PREFIX}{region}"


def is_power(good: str) -> bool:
    return good.startswith(POWER_PREFIX)


# --- History ---------------------------------------------------------------------------------


def _histories(data: GameData) -> tuple[AnnualHistory, ...]:
    return data.commodity_history.goods if data.commodity_history else ()


def _power(data: GameData) -> tuple[AnnualHistory, ...]:
    return data.power_history.regions if data.power_history else ()


def history_of(data: GameData, good: str) -> AnnualHistory:
    if is_power(good):
        assert data.power_history is not None
        return data.power_history.region(good.removeprefix(POWER_PREFIX))
    assert data.commodity_history is not None
    return data.commodity_history.good(good)


def mean_of(data: GameData, good: str) -> float:
    """The index's base: the 2010-2019 mean price (power: 1.0, the index itself)."""
    return 1.0 if is_power(good) else history_of(data, good).mean_2010_2019


def history_month(history: AnnualHistory, key: str, turn: int, mean: float) -> GoodMonth | None:
    """A good's month from history, or None after it ends. A history shortage's first month is
    `shock_turn` (contracts signed before it keep 100%, as 26.2)."""
    if not 0 <= turn <= history.last_turn:
        return None
    index = history.value_at(turn) / mean
    allocation = history.allocation_at(turn)
    start = history.shortage_start(turn)
    return GoodMonth(
        good=key,
        turn=turn,
        index=index,
        allocation=allocation,
        base=index,
        change=0.0,
        shock_turn=start,
        shock_months=0 if start is None else turn - start + 1,
        shock_allocation=allocation,
    )


# --- After 2025 ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Draws:
    z: float  # standard normal: the AR(1) step
    start: float  # uniform: does a shock start
    kind: float  # uniform: which kind
    rise: float
    allocation: float
    months: float


def draws(rng: RngFactory, turn: int, good_index: int) -> Draws:
    gen = rng.stream(turn, "commodity", COMMODITY_KEY, good_index)
    z = float(gen.standard_normal())
    start, kind, rise, allocation, months = (float(x) for x in gen.random(UNIFORMS))
    return Draws(z, start, kind, rise, allocation, months)


def monthly_phi(phi: float) -> float:
    return float(phi ** (1 / MONTHS_PER_YEAR))


def monthly_sd(vol: float) -> float:
    return vol / math.sqrt(MONTHS_PER_YEAR)


def ar1_step(base: float, level: float, phi: float, vol: float, z: float) -> float:
    """One month of the log AR(1) toward `level` (annual persistence and volatility)."""
    pm = monthly_phi(phi)
    return math.exp(math.log(level) + pm * (math.log(base) - math.log(level)) + monthly_sd(vol) * z)


def shock_chances(cb: CommodityBalance, top_share: float) -> list[tuple[str, float]]:
    """Each kind's monthly chance for a good (export bans likelier where concentrated)."""
    concentrated = top_share > cb.ban_concentration
    return [
        (kind, s.monthly * (s.concentrated_mult if concentrated else 1.0))
        for kind, s in cb.shocks.items()
    ]


def _lerp(lo: float, hi: float, u: float) -> float:
    return lo + (hi - lo) * u


def step_commodity(
    prev: GoodMonth,
    turn: int,
    d: Draws,
    level: float,
    vol: float,
    top_share: float,
    cb: CommodityBalance,
) -> GoodMonth:
    """The month after `prev` from this month's draws (33.1)."""
    base = ar1_step(prev.base, level, cb.phi, vol, d.z)
    month = replace(prev, turn=turn, base=base, change=0.0)
    if not prev.in_shock(turn):
        ended = None if prev.shock_turn is None else prev.shock_turn + prev.shock_months
        free = ended is None or turn - ended >= cb.gap_months
        chances = shock_chances(cb, top_share)
        total = sum(p for _, p in chances)
        if free and d.start < total:
            pick = d.kind * total
            kind = chances[-1][0]
            for name, p in chances:
                if pick < p:
                    kind = name
                    break
                pick -= p
            s = cb.shocks[kind]
            span = int(s.months.hi) - int(s.months.lo) + 1
            month = replace(
                month,
                shock_turn=turn,
                shock_kind=kind,
                shock_rise=_lerp(s.rise.lo, s.rise.hi, d.rise),
                shock_allocation=_lerp(s.allocation.lo, s.allocation.hi, d.allocation),
                shock_months=int(s.months.lo) + min(span - 1, math.floor(d.months * span)),
            )
    allocation = month.shock_allocation if month.in_shock(turn) else 1.0
    return replace(month, index=base * (1 + shock_premium(month, turn)), allocation=allocation)


def step_power(
    prev: GoodMonth, turn: int, z: float, level: float, pb_phi: float, vol: float
) -> GoodMonth:
    base = ar1_step(prev.base, level, pb_phi, vol, z)
    return replace(prev, turn=turn, index=base, base=base, allocation=1.0, change=0.0)


def _start_from(prev: GoodMonth | None, last: GoodMonth, turn: int) -> GoodMonth:
    """The month to step from: the state's month before, else history's last (a save made
    before M17, or a gap)."""
    if prev is not None and prev.turn == turn - 1:
        return prev
    start = prev if prev is not None and last.turn < prev.turn < turn - 1 else last
    if start is last:
        start = replace(last, shock_turn=None, shock_months=0, shock_kind=None)
    return replace(start, turn=turn - 1)


def commodity_month(
    state: GameState,
    i: int,
    history: AnnualHistory,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> GoodMonth:
    turn = state.turn
    mean = history.mean_2010_2019
    known = history_month(history, history.key, turn, mean)
    if known is not None:
        return known
    last = history_month(history, history.key, history.last_turn, mean)
    assert last is not None and data.commodities is not None
    prev = _start_from(state.good_month(history.key), last, turn)
    cb = balance.commodity
    top = data.commodities.good(history.key).top_share
    level = history.long_run / mean
    return step_commodity(prev, turn, draws(rng, turn, i), level, cb.vol[history.key], top, cb)


def power_month(
    state: GameState, i: int, history: AnnualHistory, rng: RngFactory, balance: Balance
) -> GoodMonth:
    turn = state.turn
    key = power_key(history.key)
    known = history_month(history, key, turn, 1.0)
    if known is not None:
        return known
    last = history_month(history, key, history.last_turn, 1.0)
    assert last is not None
    prev = _start_from(state.good_month(key), last, turn)
    pb = balance.power
    if history.key == pb.base_region:
        return replace(prev, turn=turn, index=1.0, base=1.0, allocation=1.0)
    z = float(rng.stream(turn, "commodity", POWER_KEY, i).standard_normal())
    return step_power(prev, turn, z, history.mean_2010_2019, pb.phi, pb.vol)


def months(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GoodMonth, ...]:
    """Phase 4 (with M12a's goods): every commodity's and region's power month, sorted by key
    (the order a loaded state has, after M12a's goods)."""
    out = [commodity_month(state, i, h, rng, balance, data) for i, h in enumerate(_histories(data))]
    out += [power_month(state, i, h, rng, balance) for i, h in enumerate(_power(data))]
    return tuple(sorted(out, key=lambda g: g.good))


# --- What the player sees (never a month ahead) ---------------------------------------------


def current(state: GameState, good: str, data: GameData) -> GoodMonth:
    """The month the player is in: history while there is history, else the latest month
    phase 4 set that is not after the state's turn (as M12r's components)."""
    history = history_of(data, good)
    mean = mean_of(data, good)
    known = history_month(history, good, state.turn, mean)
    if known is not None:
        return known
    latest = state.good_month(good)
    if latest is not None and latest.turn <= state.turn:
        return latest
    last = history_month(history, good, history.last_turn, mean)
    assert last is not None
    return last


def index_now(state: GameState, good: str, data: GameData) -> float:
    return current(state, good, data).index


def price_multiple(good: str, balance: Balance) -> float:
    """Semiconductor-grade polysilicon is solar spot x the multiple (33.1)."""
    return balance.commodity.semi_poly_multiple if good == "polysilicon" else 1.0


def price(state: GameState, key: str, turn: int, data: GameData, balance: Balance) -> float:
    """**Interface for M18.** A commodity's price in `turn` in its history's unit (dollars a
    tonne for lithium carbonate, US cents a pound for copper; polysilicon at semiconductor
    grade). History for any month to December 2025; after it, only the state's current month
    (the latest the engine has made). A month after the state's raises FutureMonthError."""
    if turn > state.turn:
        raise FutureMonthError(f"{key}: month {turn} is after the game's month {state.turn}")
    history = history_of(data, key)
    mean = mean_of(data, key)
    month = history_month(history, key, turn, mean)
    if month is None:
        latest = current(state, key, data)
        if latest.turn != turn:
            raise FutureMonthError(f"{key}: month {turn} is not held (only {latest.turn})")
        month = latest
    return month.index * mean * price_multiple(key, balance)


@dataclass(frozen=True, slots=True)
class PriceDeck:
    """The price deck a feasibility study uses (33, M18): the current price and the long-run
    level, in the good's unit and in dollars a volume unit."""

    key: str
    unit: str
    volume_unit: str
    current: float  # this month's price, in `unit`
    long_run: float  # the 2015-2025 median the seeded path reverts to, in `unit`
    current_usd: float  # dollars a volume unit (a tonne, a kilogram, a lot)
    long_run_usd: float


def deck(state: GameState, key: str, data: GameData, balance: Balance) -> PriceDeck:
    """**Interface for M18.** The price deck for a commodity in the state's month."""
    assert data.commodities is not None
    good = data.commodities.good(key)
    history = history_of(data, key)
    mult = price_multiple(key, balance)
    now = price(state, key, state.turn, data, balance)
    long_run = history.long_run * mult
    return PriceDeck(
        key=key,
        unit=good.unit,
        volume_unit=good.volume_unit,
        current=now,
        long_run=long_run,
        current_usd=now * good.usd_per_unit,
        long_run_usd=long_run * good.usd_per_unit,
    )
