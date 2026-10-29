"""Rival formulas (docs/formulas.md section 15): needs, utility, pool sizing, poach odds.

Pure functions of numbers; the phases in this package gather the inputs from the state.
"""

from __future__ import annotations

import math

from tst.sim.data_models import PoachBalance, RivalNeedBalance, RivalsBalance
from tst.sim.money import BP_DENOMINATOR


def clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


# --- Needs (15.3) -----------------------------------------------------------------------------


def need_price_cut(drop: float, need: RivalNeedBalance) -> float:
    """Share of served customers lost over the window: drop / 0.05."""
    return clamp01(drop / need.price_cut_drop)


def need_price_rise(lead: float, share_falling: bool, need: RivalNeedBalance) -> float:
    """Appeal lead over the next best product, share not falling: (lead - 5) / 10."""
    if share_falling:
        return 0.0
    return clamp01((lead - need.price_rise_lead) / need.price_rise_span)


def need_gap(best: float, own: float, divisor: float) -> float:
    """(best in segment - own) / divisor: feature 15, quality 15, brand 30."""
    return clamp01((best - own) / divisor)


def need_enter(unserved_fraction: float, cash_months: float, need: RivalNeedBalance) -> float:
    """(unserved / D - 0.4) / 0.4, with cash for at least 12 months of costs."""
    if unserved_fraction < need.enter_unserved or cash_months < need.enter_cash_months:
        return 0.0
    return clamp01((unserved_fraction - need.enter_unserved) / need.enter_span)


def need_cut_costs(cash_months: float, need: RivalNeedBalance) -> float:
    """(12 - months) / 6 while cash covers fewer than 12 months of costs."""
    return clamp01((need.cut_costs_months - cash_months) / need.cut_costs_span)


def need_poach(gain: float, has_target: bool, need: RivalNeedBalance) -> float:
    """The player's share gain over the window in a shared segment: gain / 0.05."""
    return clamp01(gain / need.poach_gain) if has_target else 0.0


def utility(need: float, weight: float, noise: float) -> float:
    """U(a) = need(a) x w_personality(a) + N(0, 0.1)."""
    return need * weight + noise


# --- Pools (15.1) -----------------------------------------------------------------------------


def pool_budget_cents(
    revenue_cents: float, margin_bp: int, hosting_cents: float, marketing_cents: float
) -> float:
    """Monthly cost budget = revenue x (1 - margin) - hosting - marketing, never below 0."""
    return max(
        0.0, revenue_cents * (1 - margin_bp / BP_DENOMINATOR) - hosting_cents - marketing_cents
    )


def rounded_headcount(headcount: float, rv: RivalsBalance) -> int:
    """Shown headcount: rounded to the nearest 10 above 100 (15.5)."""
    n = round(headcount)
    if n > rv.headcount_round_above:
        return int(round(n / rv.headcount_round) * rv.headcount_round)
    return n


def money_label(cash_months: float | None, rv: RivalsBalance) -> str:
    """deep pockets (36 months or more), comfortable (12-36), tight (under 12) (15.5)."""
    if cash_months is None or cash_months >= rv.money_bands_months.hi:
        return "deep pockets"
    if cash_months >= rv.money_bands_months.lo:
        return "comfortable"
    return "tight"


# --- Poaching (15.6) --------------------------------------------------------------------------


def poach_score(
    ratio: float, morale: float, loyalty: float, unvested: float, pb: PoachBalance
) -> float:
    """s = 4 (R - 1) + (55 - morale) / 20 - (loyalty - 10) / 10 - 2 u + leave_penalty: the
    employee's side of leaving an employer, as on the player's poach channel (M5, Reece)."""
    return (
        pb.salary_weight * (ratio - 1)
        + (pb.morale_mid - morale) / pb.morale_divisor
        - (loyalty - pb.loyalty_mid) / pb.loyalty_divisor
        - pb.options_weight * unvested
        + pb.leave_penalty
    )


def poach_probability(score: float, pb: PoachBalance) -> float:
    """p = 1 / (1 + e^(-2 s))."""
    return 1 / (1 + math.exp(-pb.steepness * score))


def poach_band(probability: float, pb: PoachBalance) -> str:
    """likely to stay (below 20%), might go (20-50%), likely to go (above 50%)."""
    if probability < pb.bands.lo:
        return "likely to stay"
    if probability <= pb.bands.hi:
        return "might go"
    return "likely to go"
