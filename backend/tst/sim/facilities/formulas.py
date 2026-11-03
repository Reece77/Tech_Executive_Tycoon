"""Pure formulas for facilities, goods and compute (docs/formulas.md 22, M12a). Every §22.8
worked example is a unit test of these functions."""

from __future__ import annotations

import math
from fractions import Fraction

from tst.sim.money import Cents, exact

RELIABILITY_MAX = 100.0  # tunable-exempt: reliability is on 0-100 (22.2)
SKILL_MAX = 20.0  # tunable-exempt: the attribute scale
OUTAGE_SPAN = 10.0  # tunable-exempt: the outage formula's divisor (22.5 definition)
EPS = 1e-9  # tunable-exempt: float tolerance
DIGITS = 9  # tunable-exempt: rounding away float noise before ceil


def capex_cents(units: int, per_unit_cents: int, index: float) -> Cents:
    """units x capex per unit (2010 $) x the input good's index (22.2)."""
    return round(units * exact(per_unit_cents) * exact(index))


def monthly_depreciation_cents(capex: Cents, life_months: int) -> Cents:
    """Straight-line over the life (22.2)."""
    return round(Fraction(capex, life_months))


def monthly_cost_cents(units: int, capex: Cents, life_months: int, opex_per_unit: int) -> Cents:
    """Depreciation plus operating cost at full use (22.8 unit cost)."""
    return monthly_depreciation_cents(capex, life_months) + units * opex_per_unit


def cost_per_used_unit_cents(monthly_cost: Cents, used: float) -> float | None:
    """The month's cost per unit used; None when nothing is used (22.8)."""
    return monthly_cost / used if used > 0 else None


def staff_needed(capacity: int, staff_per: float) -> int:
    """One infrastructure person per `staff_per` units, rounded up (22.2)."""
    return math.ceil(capacity / staff_per - EPS)


def coverage(staff: int, needed: int) -> float:
    """c_f = min(1, staff / need); a site that needs nobody is covered (22.2)."""
    return 1.0 if needed <= 0 else min(1.0, staff / needed)


def reliability(cover: float, mean_skill: float, floor: float, skill_share: float) -> float:
    """rel = 100 x c_f x (floor + share x mean skill / 20) (22.2)."""
    return RELIABILITY_MAX * cover * (floor + skill_share * mean_skill / SKILL_MAX)


def outage_chance(rel: float, base: float) -> float:
    """base x (100 - rel) / 10 a month (22.5)."""
    return max(0.0, base * (RELIABILITY_MAX - rel) / OUTAGE_SPAN)


def allocation_split(units: int, allocation: float, delay_step: float) -> tuple[int, int, int]:
    """(on time, late, months late) for a build at `allocation` (22.4): the allocated share
    on time, the rest one month later per `delay_step` of shortfall."""
    if allocation >= 1 - EPS:
        return units, 0, 0
    on_time = round(units * exact(round(allocation, DIGITS)))
    late = units - on_time
    months = math.ceil(round((1 - allocation) / delay_step, DIGITS))
    return on_time, late, months if late else 0


def cu_need(hosting_base_cents: float, spot_cents: int) -> float:
    """A product's compute need in CU: its hosting at index 1.0 / one CU's spot price (22.1)."""
    return hosting_base_cents / spot_cents


def cumulative_depreciation_cents(
    capex: Cents, capacity: int, on_time: int, ready: int, late: int, life: int, turn: int
) -> Cents:
    """Depreciation booked up to and including `turn`: each part straight-line over `life`
    from the month it goes live (22.2). Ends at exactly `capex`."""
    if capacity <= 0:
        return 0
    months_on = min(life, max(0, turn + 1 - ready))
    months_late = min(life, max(0, turn + 1 - late))
    share = Fraction(on_time * months_on + (capacity - on_time) * months_late, capacity * life)
    return round(capex * share)


def capex_payment_cents(capex: Cents, build_months: int, paid: Cents, months_done: int) -> Cents:
    """This month's capex: equal parts, the last taking the remainder (22.2)."""
    if months_done >= build_months - 1:
        return capex - paid
    return round(Fraction(capex, build_months))


def feature_target(lead: float, base: float, per_lead: float) -> float:
    """Cloud hosting features: base + per_lead x the infrastructure lead, capped at 100 (22.3)."""
    return min(RELIABILITY_MAX, max(0.0, base + per_lead * lead))
