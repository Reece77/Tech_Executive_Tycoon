"""M32's formulas (docs/formulas.md 46), as pure functions of numbers.

Worked example (a 100 MW gas plant in North America ordered in 2030, all 2010 dollars): capex
$948/kW (the data's 2025 point, no learning) is $94.8M; at 7% over 30 years the capital recovery
factor is 0.0806, so $76.4/kW-year, plus fixed O&M $11.1 = $87.5/kW-year over 0.9 x 8,760 =
7,884 kWh a kW is $11.10/MWh; fuel at 6.226 MMBtu/MWh x $2.38/MMBtu (Henry Hub's 2025 $3.52 in
2010 dollars) is $14.82, variable O&M $2.40 and no carbon: a levelised cost of about $28.3/MWh
against North America's grid price of $68.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

HOURS_A_YEAR: Final = 8760  # tunable-exempt: calendar
KW_PER_MW: Final = 1000  # tunable-exempt: units
CENTS: Final = 100  # tunable-exempt: cents a dollar
HALF: Final = 0.5  # tunable-exempt: a median is where half have connected


def crf(rate: float, years: int) -> float:
    """The capital recovery factor: a payment a year that repays 1 over `years` at `rate`."""
    if rate <= 0:
        return 1 / years
    g = (1 + rate) ** years
    return rate * g / (g - 1)


def levelised_usd_mwh(
    capex_kw: float,
    fixed_om_kw: float,
    capacity_factor: float,
    variable_usd_mwh: float,
    rate: float,
    years: int,
) -> float:
    """46.6's plant cost a MWh: (capex x crf + fixed O&M) a kW-year over the kWh a kW makes in a
    year, plus the variable cost a MWh (fuel, variable O&M and carbon)."""
    mwh_per_kw = HOURS_A_YEAR * capacity_factor / KW_PER_MW
    if mwh_per_kw <= 0:
        return math.inf
    return (capex_kw * crf(rate, years) + fixed_om_kw) / mwh_per_kw + variable_usd_mwh


def gas_fuel_usd_mwh(heat_rate_btu_kwh: float, gas_usd_mmbtu: float) -> float:
    """Btu/kWh = MMBtu a MWh / 1,000 x 1,000: heat rate / 1,000 MMBtu a MWh x the gas price."""
    return heat_rate_btu_kwh / KW_PER_MW * gas_usd_mmbtu  # Btu/kWh / 1,000 = MMBtu a MWh


def ppa_price(forward_cents: float, years: int, per_year: float, cap: float) -> float:
    """46.2: the forward price less a term discount (longer terms price lower), capped."""
    # money-exact: rate
    return forward_cents * (1 - min(cap, per_year * years))


def learnt(capex: float, rate: float, years: float) -> float:
    """A type's capex after `years` of its seeded yearly decline (46.2, after 2025)."""
    return float(capex * (1 - rate) ** max(0.0, years))


def irr(
    flows: Sequence[float],
    lo: float = -0.99,  # tunable-exempt: the bisection's lowest rate
    hi: float = 1.0,
    tol: float = 1e-7,  # tunable-exempt: the bisection's tolerance
) -> float:
    """The rate at which the flows' present value is zero (bisection; flows[0] the outlay).
    Returns `lo` if even `lo` leaves the value negative, `hi` if `hi` leaves it positive."""

    def npv(r: float) -> float:
        return sum(f / (1 + r) ** t for t, f in enumerate(flows))

    if npv(lo) < 0:
        return lo
    if npv(hi) > 0:
        return hi
    a, b = lo, hi
    while b - a > tol:
        m = (a + b) / 2
        if npv(m) > 0:
            a = m
        else:
            b = m
    return (a + b) / 2


def hazard(median_months: float, min_share: float) -> float:
    """A queued project's monthly chance of connecting after `min_share` x the median, set so
    the median wait is the region's: after the minimum the remaining wait is geometric with a
    median of median x (1 - min_share)."""
    rest = max(1.0, median_months * (1 - min_share))
    return float(1 - HALF ** (1 / rest))


def overrun(lo: float, hi: float, u: float, skew: float) -> float:
    """A plant's hidden capex overrun: lo + (hi - lo) x u ^ skew (most near the quote)."""
    return float(lo + (hi - lo) * u**skew)
