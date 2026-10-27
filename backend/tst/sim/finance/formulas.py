"""Finance formulas (docs/formulas.md section 14). Pure functions of their arguments.

Share arithmetic uses exact fractions and rounds half-to-even only where a share count is
stored, so a round closes to the share (14.10). Money stays integer cents.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import BoardBalance, FinanceBalance, SafeBalance
from tst.sim.money import BP_DENOMINATOR, Cents

type Hint = Literal["likely", "uncertain", "unlikely"]


def round_shares(value: Fraction | float) -> int:
    """Share counts are integers, rounded half-to-even (14.2)."""
    return round(value)


# --- 14.2 Shares, vesting and retention ------------------------------------------------------


def shares_for_bp(bp: int, fd_shares: int) -> int:
    """An offer's equity in bp of the current FD as options: round(bp x FD / 10000)."""
    return round_shares(Fraction(bp * fd_shares, BP_DENOMINATOR))


def vested_shares(granted: int, months: int, fb: FinanceBalance) -> int:
    """0 before the cliff, then floor(granted x min(vesting, months) / vesting)."""
    if months < fb.cliff_months:
        return 0
    return granted * min(fb.vesting_months, months) // fb.vesting_months


def retention_factor(
    unvested: int, price: Fraction, annual_salary_cents: Cents, fb: FinanceBalance
) -> float:
    """max(floor, 1 - slope x u), with u = unvested x share price / annual salary."""
    if unvested <= 0 or price <= 0 or annual_salary_cents <= 0:
        return 1.0
    u = float(unvested * price / annual_salary_cents)
    return max(fb.retention_floor, 1 - fb.retention_slope * u)


# --- 14.3 Investors' view of value -----------------------------------------------------------


def growth_6(mrr_now: Cents, mrr_then: Cents, fb: FinanceBalance) -> float:
    """Annualized 6-month MRR growth: (MRR_t / MRR_t-6)^(12/6) - 1, with the edge cases."""
    if mrr_now <= 0:
        return 0.0
    if mrr_then <= 0:
        return fb.new_revenue_growth
    exponent = MONTHS_PER_YEAR / fb.growth_window_months
    return float((mrr_now / mrr_then) ** exponent - 1)


def arr_multiple(g6: float, climate: float, fb: FinanceBalance) -> float:
    raw = fb.multiple_base + fb.multiple_per_growth * g6
    return min(max(raw, fb.multiple_min), fb.multiple_max) * climate


def value_floor_cents(live_product: bool, headcount: int, fb: FinanceBalance) -> Cents:
    base = fb.floor_cents.live if live_product else fb.floor_cents.no_product
    return base + fb.floor_per_head_cents * min(headcount, fb.floor_head_cap)


def base_value_cents(
    arr_cents: Cents,
    g6: float,
    climate: float,
    live_product: bool,
    headcount: int,
    fb: FinanceBalance,
) -> Cents:
    """V_base = max(V_floor, ARR x multiple). Never shown (14.9)."""
    traction = round(arr_cents * arr_multiple(g6, climate, fb))
    return max(value_floor_cents(live_product, headcount, fb), traction)


# --- 14.4 SAFEs ------------------------------------------------------------------------------


def safe_ratio(base_cents: Cents, cap_cents: Cents, sb: SafeBalance) -> float:
    """optimism x V_base / cap: 1 is an even chance."""
    return sb.optimism * base_cents / cap_cents


def safe_probability(base_cents: Cents, cap_cents: Cents, sb: SafeBalance) -> float:
    """p = 1 / (1 + exp(-steepness x (optimism x V_base / cap - 1))). Never shown (14.9)."""
    x = sb.steepness * (safe_ratio(base_cents, cap_cents, sb) - 1)
    return 1 / (1 + math.exp(-x))


def safe_hint(base_cents: Cents, cap_cents: Cents, sb: SafeBalance) -> Hint:
    """The SAFE dialog's band (14.9): likely, uncertain or unlikely."""
    ratio = safe_ratio(base_cents, cap_cents, sb)
    if ratio >= sb.hint_bands.hi:
        return "likely"
    if ratio >= sb.hint_bands.lo:
        return "uncertain"
    return "unlikely"


def safe_fraction(safes: list[tuple[Cents, Cents]]) -> Fraction:
    """f = sum of amount / cap over outstanding post-money SAFEs (ADR-0018 section 2)."""
    return sum((Fraction(amount, cap) for amount, cap in safes), Fraction(0))


# --- 14.5 Priced rounds ----------------------------------------------------------------------


def quoted_pre_money_cents(base_cents: Cents, bias: float, z: float, sd: float) -> Cents:
    """V_pre = V_base x bias x exp(N(0, sd)), with z a standard normal draw."""
    return round(base_cents * bias * math.exp(sd * z))


def offered_amount_cents(
    target_cents: Cents,
    check_min_cents: Cents,
    check_max_cents: Cents,
    pre_money_cents: Cents,
    max_of_pre: float,
) -> Cents:
    """clamp(target, check_min, min(check_max, max_of_pre x V_pre))."""
    hi = min(check_max_cents, round(max_of_pre * pre_money_cents))
    return min(max(target_cents, check_min_cents), max(hi, check_min_cents))


def response_chance(response: float, climate: float, cap: float) -> float:
    return min(response * climate, cap)


def round_fee_cents(amount_cents: Cents, min_cents: Cents, fee_bp: int) -> Cents:
    """max(minimum, fee_bp of the amount)."""
    return max(min_cents, amount_cents * fee_bp // BP_DENOMINATOR)


@dataclass(frozen=True, slots=True)
class Closing:
    """The share counts of a priced round's close (14.5)."""

    pool_shares: int  # X, the pool top-up
    safe_shares: int  # C, the SAFE conversion
    new_shares: int  # N, the new preferred
    fd_pre: int  # E + X + C
    price: Fraction  # V_pre / FD_pre, dollars-in-cents per share

    @property
    def fd_after(self) -> int:
        return self.fd_pre + self.new_shares


def close_round(
    fd_before: int,
    safe_frac: Fraction,
    unallocated: int,
    pre_money_cents: Cents,
    amount_cents: Cents,
    pool_target: Fraction,
) -> Closing:
    """k = t V_post / (V_pre (1 - f)), X = max(0, (kE - u) / (1 - k)), C = f / (1 - f) (E + X),
    price = V_pre / (E + X + C), N = amount / price (ADR-0018 section 3)."""
    post = pre_money_cents + amount_cents
    k = pool_target * post / (pre_money_cents * (1 - safe_frac))
    x = round_shares(max(Fraction(0), (k * fd_before - unallocated) / (1 - k)))
    c = round_shares(safe_frac / (1 - safe_frac) * (fd_before + x))
    fd_pre = fd_before + x + c
    price = Fraction(pre_money_cents, fd_pre)
    n = round_shares(amount_cents / price)
    return Closing(pool_shares=x, safe_shares=c, new_shares=n, fd_pre=fd_pre, price=price)


# --- 14.6 The board --------------------------------------------------------------------------


def runway_points(runway_months: float | None, bb: BoardBalance) -> float:
    """R from the runway in months; None (profitable) counts as the longest runway."""
    if runway_months is None:
        return bb.runway_terms[0].points
    for term in bb.runway_terms:
        if runway_months >= term.min_months:
            return term.points
    return bb.runway_terms[-1].points


def growth_points(g6: float, expected: float, bb: BoardBalance) -> float:
    """growth_weight x clamp(g6 / g_exp - 1, -1, 1)."""
    return bb.growth_weight * min(max(g6 / expected - 1, -1.0), 1.0)


def confidence_target(growth: float, runway: float, patience: float, bb: BoardBalance) -> float:
    return bb.target_base + growth + runway + patience


def clamp_confidence(confidence: float) -> float:
    return min(max(confidence, 0.0), 100.0)


def next_confidence(confidence: float, target: float, bb: BoardBalance) -> float:
    """B <- B + rate (T - B), kept in 0..100."""
    return clamp_confidence(confidence + bb.rate * (target - confidence))


def confidence_label(confidence: float, bb: BoardBalance) -> str:
    """Words for the board's mood: confident, watchful or losing patience."""
    if confidence < bb.warning_below:
        return "losing patience"
    if confidence < bb.start:
        return "watchful"
    return "confident"
