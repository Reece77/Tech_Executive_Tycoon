"""Small research formulas with no state (docs/formulas.md 21.5)."""

from __future__ import annotations

from tst.sim.data_models import Balance
from tst.sim.money import Cents, exact, pct_of


def license_price_cents(points: float, arr_cents: Cents, balance: Balance) -> Cents:
    """rnd.license.price_per_point x points x (1 + ARR / $20M), once (21.5); ARR is the
    licensee's."""
    lic = balance.rnd.license
    arr = 1 + exact(arr_cents) / lic.price_arr_cents
    price = exact(lic.price_per_point_cents) * exact(points) * arr
    return round(price)


def royalty_cents(revenue_cents: Cents, balance: Balance) -> Cents:
    """rnd.license.royalty_bp of a month's revenue in the domain's categories (21.5)."""
    return pct_of(revenue_cents, balance.rnd.license.royalty_bp)
