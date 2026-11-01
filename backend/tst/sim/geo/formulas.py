"""Geography formulas (docs/formulas.md 19, M9). Pure arithmetic; money in integer cents."""

from __future__ import annotations

from fractions import Fraction

from tst.sim.data_models import Balance, CityDef, GameData
from tst.sim.money import Cents, exact, pct_of


def round_cents(value: Fraction) -> Cents:
    """Round half to even, once, at the end (ADR-0003)."""
    return round(value)


def flexible_seat_cents(rent_index: float, balance: Balance) -> Cents:
    """Flexible space: `$600 x rent index` a head a month (19.2, 8)."""
    return round_cents(exact(balance.payroll.office_cost_per_head_cents) * exact(rent_index))


def lease_rent_cents(seats: int, rent_index: float, balance: Balance) -> Cents:
    """A lease: `seats x $600 x rent index x lease_discount` a month, full or not (19.2)."""
    return round_cents(
        seats
        * exact(balance.payroll.office_cost_per_head_cents)
        * exact(rent_index)
        * exact(balance.office.lease_discount)
    )


def fit_out_cents(rent_cents: Cents, balance: Balance) -> Cents:
    """Fit-out: fit_out_months of rent, once (19.2)."""
    return rent_cents * balance.office.fit_out_months


def close_penalty_cents(rent_cents: Cents, balance: Balance) -> Cents:
    """Closing: close_penalty_months of rent, once (19.2)."""
    return rent_cents * balance.office.close_penalty_months


def pay_multiplier_bp(city: CityDef, balance: Balance) -> int:
    """The multiplier people working in a city are paid at: its salary multiplier x
    geo.pay_level, the calibration that makes a San Francisco company's average pay equal
    v1's regional mix (19.1). Asks and market rates both use it."""
    return round(exact(city.salary_multiplier_bp) * exact(balance.geo.pay_level))


def city_market_mid_cents(band_mid_cents: Cents, city: CityDef, balance: Balance) -> Cents:
    """A market rate in a city: band mid x the city's pay multiplier (19.1, 2)."""
    return pct_of(band_mid_cents, pay_multiplier_bp(city, balance))


def localization_cents(scope: float, balance: Balance) -> Cents:
    """`$40,000 x sigma / 6`, once per region (19.5)."""
    mb = balance.markets
    return round_cents(exact(mb.localize_cents) * exact(scope) / exact(mb.localize_scope))


def cross_region_factor(regions: int, balance: Balance) -> float:
    """`max(0.85, 1 - 0.05 x (regions - 1))` for builders in `regions` regions (19.4)."""
    mb = balance.markets
    if regions <= 1:
        return 1.0
    return max(mb.cross_region_floor, 1 - mb.cross_region_step * (regions - 1))


def relative_row(region: str, home: str, data: GameData) -> tuple[float, float]:
    """(size, price index) of `region` relative to the home region's row (19.5)."""
    row, base = data.region_market(region), data.region_market(home)
    return row.size / base.size, row.price_index / base.price_index


def regional_d0(home_d0: float, region: str, home: str, data: GameData) -> float:
    """`D0 = home D0 x region size` (19.5)."""
    return home_d0 * relative_row(region, home, data)[0]


def regional_price_cents(reference_cents: Cents, region: str, home: str, data: GameData) -> Cents:
    """`p_ref x price index` (19.5)."""
    return max(1, round_cents(exact(reference_cents) * exact(relative_row(region, home, data)[1])))


def talent_bonus(city: CityDef, skill: str, data: GameData) -> float:
    """A city's talent bonus for one skill: the skill's own entry, else its group's (19.1)."""
    if skill in city.talent:
        return city.talent[skill]
    group = next(s.group for s in data.skills if s.key == skill)
    return city.talent.get(group, 0.0)


def regional_growth(category_growth: float, region: str, data: GameData) -> float:
    """A region's annual growth: the category's x the region's multiplier (19.5)."""
    return category_growth * data.region_growth.get(region, 1.0)
