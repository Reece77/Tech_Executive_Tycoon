"""Money is integer US cents (ADR-0003). Never use float for money."""

from __future__ import annotations

import re
from collections.abc import Iterable
from fractions import Fraction
from typing import Final

from tst.sim.errors import InvalidMoneyError

type Cents = int

CENTS_PER_DOLLAR: Final = 100
BP_DENOMINATOR: Final = 10_000  # tunable-exempt: definition of a basis point
DECIMAL_BASE: Final = 10  # tunable-exempt: the base of a decimal (M36p: n / DECIMAL_BASE**k)

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


def format_money(amount: Cents) -> str:
    """$1,234.56 style; negative amounts as -$1,234.56 (CLI and inbox text)."""
    sign = "-" if amount < 0 else ""
    dollars, rest = divmod(abs(amount), CENTS_PER_DOLLAR)
    return f"{sign}${dollars:,}.{rest:02d}"


def exact(x: float | int | Fraction) -> Fraction:
    """A number as the exact rational it was written as: 0.1 is 1/10, not the nearest binary
    float. Money arithmetic runs in Fractions and rounds half-to-even once, at the end
    (ADR-0003; M8r, Codex review 1 finding 6)."""
    if isinstance(x, Fraction | int):
        return Fraction(x)
    numerator, places = scaled(x)
    return Fraction(numerator, DECIMAL_BASE**places)


def scaled(x: float) -> tuple[int, int]:
    """(n, k) with x == n / 10**k exactly as `exact` reads x (its shortest repr), k >= 0: the
    integer numerator money arithmetic multiplies without building a Fraction (M36p)."""
    text = float.__repr__(x)
    mantissa, _, power = text.partition("e")
    whole, _, frac = mantissa.partition(".")
    numerator = int(whole + frac)  # int() refuses inf and nan, as Fraction does
    places = len(frac) - (int(power) if power else 0)
    if places < 0:
        return numerator * DECIMAL_BASE**-places, 0
    return numerator, places


def round_half_even(numerator: int, denominator: int) -> int:
    """numerator / denominator (denominator > 0) rounded half to even, as round(Fraction)."""
    quotient, remainder = divmod(numerator, denominator)
    twice = 2 * remainder
    if twice > denominator or (twice == denominator and quotient % 2 == 1):
        quotient += 1
    return quotient


def times(amount: int | float | Fraction, rate: float | int | Fraction, *more: float | int) -> int:
    """Integer cents x a rate (a share, a prepayment, a fine's multiplier), and x any further
    rates, in exact rational arithmetic, rounded half to even once (ADR-0003; M23a, Codex
    review 5 finding 10). Rates are read as `exact` reads them (a non-int amount as
    `Fraction(amount)`). With int cents and int or float rates the product is one integer
    numerator over a power of ten, rounded once, with no Fraction built (M36p)."""
    if type(amount) is not int:
        return round(Fraction(amount) * exact(rate) * _product(more))
    numerator, places = amount, 0
    for factor in (rate, *more):
        if type(factor) is float:
            n, k = scaled(factor)
            numerator *= n
            places += k
        elif type(factor) is int:
            numerator *= factor
        else:
            return round(Fraction(amount) * exact(rate) * _product(more))
    return round_half_even(numerator, DECIMAL_BASE**places) if places else numerator


def exact_product(amount: int, *rates: float | int) -> Fraction:
    """amount x rates as the exact rational `times` rounds: one Fraction, built once from an
    integer numerator over a power of ten (M36p; a sum of these rounds once where posted)."""
    numerator, places = amount, 0
    for factor in rates:
        if type(factor) is float:
            n, k = scaled(factor)
            numerator *= n
            places += k
        elif type(factor) is int:
            numerator *= factor
        else:
            return Fraction(amount) * _product(rates)
    return Fraction(numerator, DECIMAL_BASE**places)


def sum_times(rows: Iterable[tuple[int, float | int]]) -> int:
    """sum(amount x rate) over (int cents, rate) rows, exactly, rounded half to even once:
    round(sum(Fraction(amount) * exact(rate))), with no Fraction built for int cents and
    int or float rates (M36p)."""
    rows = list(rows)
    if not all(type(a) is int and type(r) in (int, float) for a, r in rows):
        return round(sum((Fraction(a) * exact(r) for a, r in rows), Fraction()))
    total, places = 0, 0
    for amount, rate in rows:
        n, k = scaled(rate) if type(rate) is float else (int(rate), 0)
        term = amount * n
        if k > places:
            total *= DECIMAL_BASE ** (k - places)
            places = k
        elif k < places:
            term *= DECIMAL_BASE ** (places - k)
        total += term
    return round_half_even(total, DECIMAL_BASE**places) if places else total


def _product(rates: tuple[float | int, ...]) -> Fraction:
    out = Fraction(1)
    for r in rates:
        out *= exact(r)
    return out


MILLICENTS_PER_CENT: Final = 1000  # tunable-exempt: thousandths of a cent in a cent


def to_millicents(cents: float | int | Fraction) -> int:
    """A fractional cents rate (a unit fee, a wafer price) as exact integer thousandths of a
    cent, rounded half to even once (M15r, Codex review 4 finding 8)."""
    return round(exact(cents) * MILLICENTS_PER_CENT)
