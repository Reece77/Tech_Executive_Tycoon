"""Pure refining formulas (docs/formulas.md 36). No state: numbers in, numbers out.

**Unit cost** of a unit of output (36.1), in cents:

    input price x input a unit (at the effective yield)
    + MWh a unit x power price x the region's power index (33.5)
    + other variable cost
    + fixed cost a capacity unit a year / 12 / output a capacity unit a month
    + depreciation and staff over the month's output

Worked example (silicon smelter, power index 1.0, full output): quartz at $40/t x 2.5 t = $100,
12 MWh x $68 = $816, other $1,000, fixed $120 and depreciation $150 a tonne: **$2,186 a tonne**.
At South and Southeast Asia's 0.85 the power is $693.60 (**$2,063.60**); at Europe's 1.5,
$1,224 (**$2,594**).
"""

from __future__ import annotations

from typing import Final

MONTHS: Final = 12  # tunable-exempt: calendar


def effective_yield(
    stated: float, semi_grade: bool, level: float, min_level: float, low: float
) -> float:
    """36.3: semiconductor grades need a process level of at least `min_level`; below it the
    yield is x `low` (halves)."""
    return stated * low if semi_grade and level < min_level else stated


def input_per_output(at_stated: float, stated: float, effective: float) -> float:
    """Input a unit of output at the effective yield: a lower yield takes more."""
    return at_stated * stated / effective if effective > 0 else 0.0


def ramp_share(turn: int, ready_turn: int, ramp_months: int) -> float:
    """Output share during the ramp after completion: (months live) / ramp_months, at most 1."""
    if turn < ready_turn:
        return 0.0
    if ramp_months <= 0:
        return 1.0
    return min(1.0, (turn - ready_turn + 1) / ramp_months)


def power_cents(mwh: float, cents_per_mwh: float, index: float) -> float:
    """A unit's power: MWh x the price at index 1.0 x the region's index (33.5)."""
    return mwh * cents_per_mwh * index


def unit_cost_cents(
    input_price_cents: float,
    input_units: float,
    mwh: float,
    cents_per_mwh: float,
    power_index: float,
    other_cents: float,
    fixed_per_unit_cents: float,
    depreciation_per_unit_cents: float = 0.0,
    staff_per_unit_cents: float = 0.0,
) -> float:
    """The module docstring's unit cost."""
    return (
        input_price_cents * input_units
        + power_cents(mwh, cents_per_mwh, power_index)
        + other_cents
        + fixed_per_unit_cents
        + depreciation_per_unit_cents
        + staff_per_unit_cents
    )


def margin(price_cents: float, unit_cost: float) -> float:
    """Operating margin at market price (36.5 target 1)."""
    return (price_cents - unit_cost) / price_cents if price_cents > 0 else 0.0


def incident_chance(
    rate_year: float,
    skill: float,
    coverage: float,
    skill_base: float,
    skill_slope: float,
    cover_base: float,
) -> float:
    """A plant's chance of an incident this month (36.4, as M19's accidents 35.4):
    `rate / 12 x (skill_base - skill_slope x skill) x (cover_base - coverage)`, at least 0."""
    factor = max(0.0, skill_base - skill_slope * skill) * max(0.0, cover_base - coverage)
    return min(1.0, rate_year / MONTHS * factor)


def derived_price_cents(
    priced_by: str,
    value: float,
    source_cents: float,
    source_index: float,
    per_source: float,
    base_cents: float,
) -> float:
    """A derived good's price (refining.config.DerivedGoodDef), cents a unit."""
    if priced_by == "share":
        return value * source_cents * per_source
    if priced_by == "divisor":
        return source_cents * per_source / value
    return base_cents * ((1 - value) + value * source_index)
