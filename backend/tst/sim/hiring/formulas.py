"""Pure formulas for docs/formulas.md sections 6-10.

No randomness: callers draw from their own stream (ADR-0013) and pass the result in. Every
number comes from `Balance` or from the scale definitions in `tst.sim.scale`.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Literal

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import (
    Balance,
    HiringBalance,
    MoraleBalance,
    OfferBalance,
    PayrollBalance,
    PeopleBalance,
    ResignBalance,
)
from tst.sim.money import BP_DENOMINATOR, Cents, pct_of
from tst.sim.scale import ATTR_MAX, ATTR_NEUTRAL, clamp_morale

type HintBand = Literal["likely", "uncertain", "unlikely"]

# --- Section 6: founder energy --------------------------------------------------------------


def energy_cost(action: str, balance: Balance) -> int:
    return balance.founder.energy_cost[action]


# --- Section 7: offers ----------------------------------------------------------------------


def offer_score(
    *,
    ratio: float,
    equity_bp: int,
    matching_interests: int,
    risk_appetite: float,
    ambition: float,
    stage: int,
    offer: OfferBalance,
    pitch: float = 0.0,
) -> float:
    """4 (R - 1) + w_eq B 0.002 m_stage + 0.5 F + A_stage - (10 - risk_appetite) / 10 + pitch.

    `pitch` is the M2 term from whoever made the offer (tst.sim.org.formulas.pitch).
    """
    w_eq = offer.w_equity * (
        offer.ambition_equity_boost if ambition > offer.ambition_boost_above else 1
    )
    return (
        offer.w_salary * (ratio - 1)
        + w_eq * equity_bp * offer.equity_value_per_bp * offer.stage_equity_mult[stage]
        + offer.w_fit * matching_interests
        + offer.stage_appeal[stage]
        - offer.w_risk * (ATTR_NEUTRAL - risk_appetite) / ATTR_NEUTRAL
        + pitch
    )


def acceptance_probability(score: float, offer: OfferBalance) -> float:
    """p = 1 / (1 + exp(-k (score - threshold)))."""
    return 1 / (1 + math.exp(-offer.k * (score - offer.threshold)))


def is_lowball(ratio: float, hiring: HiringBalance) -> bool:
    """Offers below lowball_ratio of the expectation are always declined."""
    return ratio < hiring.lowball_ratio


def hint_band(score: float, hiring: HiringBalance) -> HintBand:
    if score >= hiring.hint_bands.hi:
        return "likely"
    if score < hiring.hint_bands.lo:
        return "unlikely"
    return "uncertain"


def recruiter_fee_cents(annual_salary_cents: Cents, hiring: HiringBalance) -> Cents:
    return pct_of(annual_salary_cents, hiring.recruiter_fee_bp)


# --- Section 8: payroll ---------------------------------------------------------------------


def monthly_salary_cents(annual_salary_cents: Cents) -> Cents:
    """round(salary / 12), half to even, exact integer arithmetic."""
    return round(Fraction(annual_salary_cents, MONTHS_PER_YEAR))


def benefits_cents(monthly_salary: Cents, payroll: PayrollBalance) -> Cents:
    return pct_of(monthly_salary, payroll.benefits_bp)


def severance_cents(annual_salary_cents: Cents, payroll: PayrollBalance) -> Cents:
    return monthly_salary_cents(annual_salary_cents) * payroll.severance_months


def market_mid_cents(band_mid_cents: Cents, region_multiplier_bp: int) -> Cents:
    """Band mid for the role and level, times the region multiplier (section 9)."""
    return pct_of(band_mid_cents, region_multiplier_bp)


# --- Section 9: morale ----------------------------------------------------------------------


def pay_term(salary_cents: Cents, market_mid: Cents, morale: MoraleBalance) -> float:
    """clamp(60 x (salary / market_mid - 1), -20, +15)."""
    raw = morale.pay_slope * (salary_cents / market_mid - 1)
    return min(max(raw, morale.pay_min), morale.pay_max)


def fit_term(matching_interests: int, style_mismatch: bool, morale: MoraleBalance) -> float:
    return morale.fit_per_interest * matching_interests + (
        morale.work_style_mismatch if style_mismatch else 0
    )


def runway_term(opening_cash: Cents, current_cash: Cents, morale: MoraleBalance) -> float:
    """-10 under 6 months of runway, -20 under 3; cash <= 0 counts as under 3 months.

    Runway = current cash / (opening cash - current cash); no penalty when cash has not
    fallen this month.
    """
    if current_cash <= 0:
        return morale.runway_crit
    burn = opening_cash - current_cash
    if burn <= 0:
        return 0.0
    runway = current_cash / burn
    if runway < morale.runway_crit_months:
        return morale.runway_crit
    if runway < morale.runway_warn_months:
        return morale.runway_warn
    return 0.0


def morale_target(pay: float, fit: float, runway: float, morale: MoraleBalance) -> float:
    return morale.target_base + pay + fit + runway + morale.workload_term


def morale_noise_sd(temperament: float, morale: MoraleBalance) -> float:
    """noise_scale x (21 - temperament) / 20."""
    return morale.noise_scale * (ATTR_MAX + 1 - temperament) / ATTR_MAX


def morale_step(current: float, target: float, noise: float, morale: MoraleBalance) -> float:
    """morale + rate (target - morale) + noise, clamped to [0, 100]."""
    return clamp_morale(current + morale.rate * (target - current) + noise)


# --- Section 10 (and 3): resignation and retirement -----------------------------------------


def resignation_bp(
    morale: float,
    loyalty: float,
    job_hopper: bool,
    resign: ResignBalance,
    *,
    retention: float = 1.0,
) -> float:
    """50 x (1 + max(0, 40 - morale) / 20) x (21 - loyalty) / 10 x (2 if job hopper), times
    the M4 retention factor for unvested options (14.2), then capped."""
    chance = (
        resign.base_bp
        * (1 + max(0.0, resign.morale_floor - morale) / resign.morale_divisor)
        * (ATTR_MAX + 1 - loyalty)
        / resign.loyalty_divisor
        * (resign.job_hopper_mult if job_hopper else 1)
        * retention
    )
    return min(chance, resign.cap_bp)


def retirement_bp(age: int, people: PeopleBalance) -> float:
    """From retire_from_age: retire_bp_per_year_over_60 x (age - 59) / 12 bp per month."""
    if age < people.retire_from_age:
        return 0.0
    years = age - (people.retire_from_age - 1)
    return people.retire_bp_per_year_over_60 * years / MONTHS_PER_YEAR


def roll_succeeds(roll: int, chance_bp: float) -> bool:
    """A roll in [0, 10000) succeeds when it is below the chance (formulas.md section 0)."""
    return roll < chance_bp


ROLL_RANGE = BP_DENOMINATOR  # rolls are integers in [0, ROLL_RANGE)
