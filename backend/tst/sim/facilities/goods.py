"""Market goods: component indexes, allocation and supply shocks (docs/formulas.md 22.4).

One market-good model (ADR-0020 3): a good has a key, a unit, an index that follows
`components_history.yaml` to December 2025 (the same on every seed), then a seeded path:

- the trend's yearly change takes an AR(1) step toward `supply.change.mean` each January;
- with probability `supply.shock.monthly` a shock starts when no shock month fell in the last
  `gap_months` months: the index rises by a drawn share for a drawn number of months while
  allocation falls to a drawn level, then the rise fades over as many months.

Stream `supply`, key (good_index,): one generator per good a month, drawing in this fixed order
every month whether used or not: the yearly change's standard normal, then uniforms for the
shock's start, rise, allocation and length. `current` is the month the player is in: history
while there is history (it is public), else the last month phase 4 set. Nothing looks ahead.
v3 adds commodities as more goods.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import ComponentsHistoryFile, GoodHistory, SupplyBalance
from tst.sim.facilities.models import GoodMonth
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

MONTHS_PER_YEAR = 12  # tunable-exempt: calendar
FIRST_MONTH = 1  # tunable-exempt: January, when a good's yearly change steps
UNIFORMS = 4  # tunable-exempt: start, rise, allocation and length draws


@dataclass(frozen=True, slots=True)
class Draws:
    z: float  # standard normal: the yearly change (January only)
    start: float  # uniform: does a shock start
    rise: float  # uniform: the shock's rise
    allocation: float  # uniform: allocation while it lasts
    months: float  # uniform: how long it lasts


def _components(data: GameData) -> ComponentsHistoryFile:
    if data.components is None:
        raise RuntimeError("components_history.yaml is not loaded")
    return data.components


def history_month(good: GoodHistory, turn: int) -> GoodMonth | None:
    """A good's month from history, or None after the history ends. The yearly change is
    the index against twelve months before (the first year's, against 2010)."""
    if not 0 <= turn <= good.last_turn:
        return None
    index = good.index_at(turn)
    before = good.index_at(max(0, turn - MONTHS_PER_YEAR))
    change = index / before - 1 if turn >= MONTHS_PER_YEAR else good.index_at(MONTHS_PER_YEAR) - 1
    return GoodMonth(
        good=good.key,
        turn=turn,
        index=index,
        allocation=good.allocation_at(turn),
        base=index,
        change=change,
    )


def _lerp(lo: float, hi: float, u: float) -> float:
    return lo + (hi - lo) * u


def shock_premium(month: GoodMonth, turn: int) -> float:
    """The shock's rise on the trend in `turn`: full while it runs, then fading linearly over
    as many months as it ran (M12a decision), 0 after."""
    if month.shock_turn is None or turn < month.shock_turn:
        return 0.0
    end = month.shock_turn + month.shock_months
    if turn < end:
        return month.shock_rise
    faded = (turn - end + 1) / max(1, month.shock_months)
    return max(0.0, month.shock_rise * (1 - faded))


def shock_starts(prev: GoodMonth, turn: int, u: float, sb: SupplyBalance) -> bool:
    """A shock starts with probability `shock.monthly` if no shock month fell in the last
    `gap_months` months (22.4)."""
    s = sb.shock
    if prev.shock_turn is not None and turn - (prev.shock_turn + prev.shock_months) < s.gap_months:
        return False
    return u < s.monthly


def step_month(prev: GoodMonth, turn: int, d: Draws, sb: SupplyBalance) -> GoodMonth:
    """The month after `prev` from this month's draws (22.4)."""
    change = prev.change
    if turn % MONTHS_PER_YEAR == FIRST_MONTH - 1:  # January
        a = sb.change
        stepped = a.mean + a.phi * (prev.change - a.mean) + a.shock_sd * d.z
        change = min(a.bounds.hi, max(a.bounds.lo, stepped))
    base = prev.base * (1 + change) ** (1 / MONTHS_PER_YEAR)
    month = replace(prev, turn=turn, base=base, change=change)
    if not prev.in_shock(turn) and shock_starts(prev, turn, d.start, sb):
        s = sb.shock
        span = int(s.months.hi) - int(s.months.lo) + 1
        month = replace(
            month,
            shock_turn=turn,
            shock_rise=_lerp(s.rise.lo, s.rise.hi, d.rise),
            shock_allocation=_lerp(s.allocation.lo, s.allocation.hi, d.allocation),
            shock_months=int(s.months.lo) + min(span - 1, math.floor(d.months * span)),
        )
    allocation = month.shock_allocation if month.in_shock(turn) else 1.0
    return replace(month, index=base * (1 + shock_premium(month, turn)), allocation=allocation)


def draws(rng: RngFactory, turn: int, good_index: int) -> Draws:
    gen = rng.stream(turn, "supply", good_index)
    z = float(gen.standard_normal())
    start, rise, allocation, months = (
        float(x) for x in gen.random(UNIFORMS)
    )  # tunable-exempt: 4 uniforms
    return Draws(z, start, rise, allocation, months)


def month_for(
    good: GoodHistory,
    good_index: int,
    turn: int,
    prev: GoodMonth | None,
    rng: RngFactory,
    sb: SupplyBalance,
) -> GoodMonth:
    """A good's month in `turn`: history, else one step from the month before (from the last
    month of history when the state has no month before, e.g. a save made before M12a)."""
    known = history_month(good, turn)
    if known is not None:
        return known
    if prev is None or prev.turn != turn - 1:
        last = history_month(good, good.last_turn)
        assert last is not None
        prev = prev if prev is not None and prev.turn < turn - 1 else last
        prev = replace(prev, turn=turn - 1)
    return step_month(prev, turn, draws(rng, turn, good_index), sb)


def supply_phase(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """Phase 4: every good's month (22.4), in components_history.yaml order."""
    if data.components is None:
        return state
    months = tuple(
        month_for(good, i, state.turn, state.good_month(good.key), rng, balance.supply)
        for i, good in enumerate(data.components.goods)
    )
    return replace(state, supply=months)


def current(state: GameState, good: str, data: GameData) -> GoodMonth:
    """The month the player is in: history while there is history, else the latest month
    phase 4 set (never a month ahead, 22.6)."""
    history = _components(data).good(good)
    known = history_month(history, state.turn)
    if known is not None:
        return known
    latest = state.good_month(good)
    if latest is not None:
        return latest
    last = history_month(history, history.last_turn)
    assert last is not None
    return last


def index_now(state: GameState, good: str, data: GameData) -> float:
    return current(state, good, data).index


def allocation_now(state: GameState, good: str, data: GameData) -> float:
    return current(state, good, data).allocation
