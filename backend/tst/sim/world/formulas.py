"""The living world's formulas (docs/formulas.md 41.2, 41.6), as pure functions of numbers."""

from __future__ import annotations

import math

from tst.sim.world.config import WorldBalance


def clamp(x: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, x))


def balance_factor(demand: float, supply: float, wb: WorldBalance) -> float:
    """41.2: clamp((demand / supply) ^ elasticity, factor_min, factor_max); no supply and some
    demand is the top of the clamp, nothing on either side is 1."""
    if supply <= 0:
        return wb.factor_max if demand > 0 else 1.0
    return clamp((demand / supply) ** wb.elasticity, wb.factor_min, wb.factor_max)


def producers_output(demand: float, others: float, capacity: float, wb: WorldBalance) -> float:
    """What chain producers make a year: the demand left after `others` (the player's supply),
    inside their utilisation band of `capacity`."""
    lo, hi = wb.utilisation.lo * capacity, wb.utilisation.hi * capacity
    return clamp(demand - others, lo, hi)


def normal_supply(capacity: float, player: float, wb: WorldBalance) -> float:
    """41.2's supply: chain producers' live capacity at `base_utilisation` (normal running)
    plus the player's output to the market."""
    return capacity * wb.base_utilisation + player


def unit_cash_cost(long_run: float, cost: float, power_index: float, wb: WorldBalance) -> float:
    """A unit's cash cost (41.1): the long-run price x the cost position's share of it, the
    power share moving with the region's power index."""
    share = wb.cost_range.lo + (wb.cost_range.hi - wb.cost_range.lo) * cost
    return long_run * share * (1 - wb.power_share + wb.power_share * power_index)


def unit_full_cost(long_run: float, cash: float, wb: WorldBalance) -> float:
    """Cash cost plus fixed costs and the capital's straight-line charge a unit (41.2's cost
    per unit for the hurdle): the expansion is judged on what a new unit costs to own."""
    return cash + long_run * (wb.fixed_share + wb.capex_years / wb.life_years)


def outlook(prices: tuple[float, ...], long_run: float, wb: WorldBalance) -> float:
    """41.2's 3-year displayed price outlook before the balance factor: a year of spot (the last
    12 months' mean) and two of the long-run level, as M18's deck."""
    spot = sum(prices) / len(prices) if prices else long_run
    return wb.outlook_spot_weight * spot + (1 - wb.outlook_spot_weight) * long_run


def phase_effect(depth: float, months: int, k: int) -> float:
    """A recession's or boom's effect `k` months in (0-based) of `months`: a sine arch peaking at
    `depth` mid-phase (41.6: in and out over its months)."""
    if months <= 0 or not 0 <= k < months:
        return 0.0
    return depth * math.sin(math.pi * (k + 1) / (months + 1))


def ar1_level(level: float, phi: float, sd: float, z: float) -> float:
    return 1 + phi * (level - 1) + sd * z


def lerp(lo: float, hi: float, u: float) -> float:
    return lo + (hi - lo) * u


def whole_months(lo: float, hi: float, u: float) -> int:
    span = int(hi) - int(lo) + 1
    return int(lo) + min(span - 1, math.floor(u * span))
