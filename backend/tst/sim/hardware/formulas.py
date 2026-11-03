"""Pure formulas for hardware (docs/formulas.md 26.1-26.2, M12b). Every 26.7 hardware
worked example is a unit test of these functions. Money in cents; per-unit costs may be
fractional cents (they are rounded once, when a month's cost posts)."""

from __future__ import annotations

from tst.sim.facilities import formulas as ff
from tst.sim.money import Cents

SKILL_MAX = 20.0  # tunable-exempt: the attribute scale


def bom_cents(base_cents: int, index: float) -> float:
    """bom = bom_base x the good's index (26.2)."""
    return base_cents * index


def device_unit_cents(bom: float, chip: float, assembly: float) -> float:
    """BOM + chip + assembly (26.2): $180 + $40 + $13 = $233 (26.7)."""
    return bom + chip + assembly


def contract_fee_cents(base_fee: int, manufacturer_mult: float, city_mult: float) -> float:
    """A contract manufacturer's fee a unit: the base (Shenzhen) x the manufacturer's and
    city's multipliers (26.2)."""
    return base_fee * manufacturer_mult * city_mult


def take_or_pay_cents(unused_units: float, fee: float, share: float) -> Cents:
    """share of the fee on each unused unit of a month's volume (26.2: 50%)."""
    return round(max(0.0, unused_units) * fee * share)


def plant_yield(base: float, skill_share: float, mean_skill: float) -> float:
    """yield = 0.85 + 0.10 x mean manufacturing skill / 20 (26.2)."""
    return base + skill_share * mean_skill / SKILL_MAX


def plant_cost_per_good_unit(
    capacity: int,
    used: float,
    yield_rate: float,
    fixed_cents: int,
    variable_cents: int,
    capex_cents: Cents,
    life_months: int,
) -> float | None:
    """(fixed + variable x units run + depreciation) / good units (26.2, 26.7): a 20,000
    unit plant at 80% use and yield 0.92 costs $8.87 a good unit. None when nothing runs."""
    good = used * yield_rate
    if good <= 0:
        return None
    depreciation = ff.monthly_depreciation_cents(capex_cents, life_months)
    del capacity  # the capacity sets capex; kept for the signature's readability
    return (fixed_cents + variable_cents * used + depreciation) / good


def capacity_allocation(contracted: float, allocation: float, protected: bool) -> float:
    """Units a contract delivers this month: all of them when it was signed before the
    shortage began, else the good's allocation share (26.2)."""
    return contracted if protected else contracted * allocation
