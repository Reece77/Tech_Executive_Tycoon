"""Mining arithmetic (docs/formulas.md 35.2-35.4): pure functions of numbers and balance.yaml."""

from __future__ import annotations

import math

from tst.sim.mining.config import AccidentBalance, MiningBalance, SubtypeBalance

LB_PER_T = 2204.62  # tunable-exempt: unit conversion, pounds a tonne
MONTHS = 12  # tunable-exempt: calendar


def capex_for(estimate_design_cents: int, capacity: float, design: float, scale: float) -> int:
    """35.2: the study's capex for its design capacity, scaled to the chosen capacity by
    (capacity / design) ** scale."""
    return round(estimate_design_cents * float((capacity / design) ** scale))


def overrun(u: float, lo: float, hi: float) -> float:
    """35.2: the hidden overrun, uniform in the study level's range."""
    return lo + (hi - lo) * u


def construction_months(u: float, lo: float, hi: float) -> int:
    """35.2: whole months, uniform in the subtype's range."""
    return round(lo + (hi - lo) * u)


def reveal_month(ordered: int, ready: int, share: float) -> int:
    """The month the cost to complete is revised: `share` of construction has passed."""
    return ordered + max(1, math.ceil((ready - ordered) * share))


def capex_payment(total: int, paid: int, months_left: int) -> int:
    """This month's capex: what is left over the months left (the last month takes the rest)."""
    if months_left <= 1:
        return max(0, total - paid)
    return max(0, round((total - paid) / months_left))


def ramp_share(sub: SubtypeBalance, months_producing: int) -> float:
    """35.2: the share of capacity in the mine's nth production month (0-based), by year."""
    year = months_producing // MONTHS
    return sub.ramp[min(year, len(sub.ramp) - 1)]


def staff_needed(capacity_t: float, per_kt: float) -> int:
    """At least one mining engineer; one per 1/per_kt thousand t a year of capacity."""
    return max(1, math.ceil(capacity_t / 1000 * per_kt))  # tunable-exempt: t to kt


def accident_factor(skill: float, coverage: float, ab: AccidentBalance) -> float:
    return max(ab.floor, ab.skill_base - ab.skill_slope * skill) * max(
        ab.floor, ab.cover_base - coverage
    )


def accident_chance(
    base_year: float, skill: float, coverage: float, safety: str, ab: AccidentBalance
) -> float:
    """35.4: a month's chance, normalised so a full crew of skill_ref at normal spend has the
    subtype's base rate a year (M19 decision)."""
    ref = accident_factor(ab.skill_ref, 1.0, ab)
    f = accident_factor(skill, coverage, ab) / ref
    return min(1.0, base_year / MONTHS * f * ab.safety_factor[safety])


def depletion_target(basis_cents: int, ore_mined: float, ore_estimate: float) -> int:
    """35.3, units of production: the share of the capitalized cost depleted so far, on the
    estimated (revealed) tonnage, never more than the whole."""
    if ore_estimate <= 0:
        return basis_cents
    return round(basis_cents * min(1.0, ore_mined / ore_estimate))


def royalty_cents(revenue_cents: int, rate: float) -> int:
    return round(revenue_cents * rate)


def usd_per_lb(usd_per_t: float) -> float:
    return usd_per_t / LB_PER_T


def ore_cost_usd_t(opex_per_t_product: float, kind_opex: float, ref: float, mult: float) -> float:
    """A t of ore's operating cost: the commodity's typical cost a t of product at the median
    grade and recovery (`ref`), so a richer deposit costs less a t of product (35.3)."""
    return opex_per_t_product * kind_opex * ref * mult


def annual_cost_usd(ore_mt: float, ore_cost: float) -> float:
    return ore_mt * 1e6 * ore_cost  # tunable-exempt: Mt to t


def fixed_month_usd(annual_usd: float, fixed_share: float, safety_cost: float) -> float:
    return annual_usd * fixed_share / MONTHS * safety_cost


def variable_usd(
    ore_t: float, ore_cost: float, fixed_share: float, energy_share: float, power: float
) -> float:
    """The month's variable cost: ore x the variable share, its energy part x power."""
    return ore_t * ore_cost * (1 - fixed_share) * ((1 - energy_share) + energy_share * power)


def reclamation_cents(product_t: float, per_t_cents: int) -> int:
    return round(product_t * per_t_cents)


def capacity_bounds(design_t: float, mb: MiningBalance) -> tuple[float, float]:
    return design_t * mb.capacity_range.lo, design_t * mb.capacity_range.hi


IRR_LO = -0.5  # tunable-exempt: the bisection's lowest rate (lower overflows 21-year flows)


def project_irr(flows: list[float], lo: float = IRR_LO, hi: float = 1.0) -> float | None:
    """The yearly IRR of yearly cash flows (bisection); None when they never change sign."""
    if not any(f < 0 for f in flows) or not any(f > 0 for f in flows):
        return None

    def npv(r: float) -> float:
        return sum(f / (1 + r) ** t for t, f in enumerate(flows))

    a, b = lo, hi
    if npv(a) * npv(b) > 0:
        return None
    for _ in range(100):  # tunable-exempt: bisection steps
        m = (a + b) / 2
        if npv(a) * npv(m) <= 0:
            b = m
        else:
            a = m
    return (a + b) / 2
