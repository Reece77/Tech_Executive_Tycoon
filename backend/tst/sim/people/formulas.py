"""Pure people formulas (docs/formulas.md sections 1-4).

No randomness here: callers draw noise from their own stream (ADR-0013) and add it.
Every number comes from `Balance` or from the scale definitions in `tst.sim.scale`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from fractions import Fraction
from typing import Final

from tst.sim.data_models import GrowthBalance, PeopleBalance, RevealBalance, band_value
from tst.sim.money import BP_DENOMINATOR, Cents
from tst.sim.scale import (
    ABILITY_PER_ATTR,
    PRIMARY_WEIGHT,
    PROFESSIONALISM_DIVISOR,
    SALARY_LEVEL_DIVISOR,
    SECONDARY_WEIGHT,
)

# Below half an attribute point the range collapses to the rounded true value (section 4).
EXACT_HALF_WIDTH: Final = 0.5  # tunable-exempt: rounding threshold in the reveal rule


# --- Section 1: current ability -------------------------------------------------------------


def current_ability(
    skills: Mapping[str, float], primary: Sequence[str], secondary: Sequence[str]
) -> float:
    """CA = 10 x (3 x sum(primary) + sum(secondary)) / (3 x n_primary + n_secondary)."""
    numerator = PRIMARY_WEIGHT * sum(skills[k] for k in primary) + SECONDARY_WEIGHT * sum(
        skills[k] for k in secondary
    )
    denominator = PRIMARY_WEIGHT * len(primary) + SECONDARY_WEIGHT * len(secondary)
    return ABILITY_PER_ATTR * numerator / denominator


# --- Section 2: generation helpers ----------------------------------------------------------


def pa_gap_mean(age: int, people: PeopleBalance) -> float:
    return band_value(people.pa_gap_mean, age)


def salary_expectation_cents(
    *,
    band_mid_cents: Cents,
    ca: float,
    level_mean: float,
    region_multiplier_bp: int,
    round_to_cents: Cents,
) -> Cents:
    """band_mid x (1 + (CA - level_mean) / 100) x region multiplier, to the nearest step.

    Exact rational arithmetic, then round half to even to a multiple of `round_to_cents`,
    so no float ever touches money.
    """
    level_term = 1 + (Fraction(ca) - Fraction(level_mean)) / SALARY_LEVEL_DIVISOR
    exact = Fraction(band_mid_cents) * level_term * Fraction(region_multiplier_bp, BP_DENOMINATOR)
    return round(exact / round_to_cents) * round_to_cents


# --- Section 3: monthly growth --------------------------------------------------------------


def growth_delta(
    *,
    in_role: bool,
    age: int,
    ca: float,
    pa: float,
    professionalism: float,
    growth: GrowthBalance,
) -> float:
    """Monthly change for one skill before noise.

    Role skills: r x a(age) x max(0, PA - CA) / PA x professionalism / 10 - d(age).
    Other skills: -d(age).
    """
    decline = band_value(growth.decline, age)
    if not in_role:
        return -decline
    headroom = max(0.0, pa - ca) / pa
    factor = band_value(growth.age_factor, age)
    return growth.rate * factor * headroom * professionalism / PROFESSIONALISM_DIVISOR - decline


# --- Section 4: revealed ranges -------------------------------------------------------------


def scout_factor(judgment_of_talent: float, reveal: RevealBalance) -> float:
    return reveal.scout_base + judgment_of_talent / reveal.scout_divisor


def narrow(hw: float, strength: float, judgment_of_talent: float, reveal: RevealBalance) -> float:
    """hw x (1 - strength x scout_factor), never below 0 and never above the old hw."""
    shrink = strength * scout_factor(judgment_of_talent, reveal)
    return hw * min(max(1 - shrink, 0.0), 1.0)


def displayed_range(
    true_value: float, hw: float, offset: float, lo: float, hi: float
) -> tuple[int, int]:
    """(min, max) shown to an observer; `lo`/`hi` are the attribute's scale bounds."""
    if hw < EXACT_HALF_WIDTH:
        exact = round(true_value)
        return exact, exact
    low = math.floor(min(max(true_value - hw * (1 + offset), lo), hi))
    high = math.ceil(min(max(true_value + hw * (1 - offset), lo), hi))
    return low, high
