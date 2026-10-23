"""Money is integer US cents (ADR-0003). Never use float for money."""

from __future__ import annotations

import re
from typing import Final

from tst.sim.errors import InvalidMoneyError

type Cents = int

CENTS_PER_DOLLAR: Final = 100
BP_DENOMINATOR: Final = 10_000  # tunable-exempt: definition of a basis point

_DOLLARS_RE: Final = re.compile(r"^(-)?\$?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?$")


def cents(dollars: str | int) -> Cents:
    """Convert whole dollars (int) or a dollar string such as "1,234.56" or "-$50" to cents."""
    if isinstance(dollars, bool):
        raise InvalidMoneyError("bool is not a money amount")
    if isinstance(dollars, int):
        return dollars * CENTS_PER_DOLLAR
    if not isinstance(dollars, str):
        raise InvalidMoneyError(f"expected str or int dollars, got {type(dollars).__name__}")
    match = _DOLLARS_RE.match(dollars.strip())
    if match is None:
        raise InvalidMoneyError(f"not a dollar amount: {dollars!r}")
    sign, whole, frac = match.groups()
    amount = int(whole.replace(",", "")) * CENTS_PER_DOLLAR + int((frac or "0").ljust(2, "0"))
    return -amount if sign else amount


def pct_of(amount: Cents, basis_points: int) -> Cents:
    """Return amount * basis_points / 10,000, rounded half to even to whole cents."""
    quotient, remainder = divmod(amount * basis_points, BP_DENOMINATOR)
    twice = 2 * remainder
    if twice > BP_DENOMINATOR or (twice == BP_DENOMINATOR and quotient % 2 == 1):
        quotient += 1
    return quotient
