"""Deterministic maths for the simulation (M35a; docs/formulas.md 0.4).

The platform's C maths library (glibc on Linux, the UCRT on Windows) may round `exp`, `log`,
`pow` and the rest differently in the last bit, so the same seed gave Windows and Linux
different games (M33). These functions are correctly rounded through `decimal` (libmpdec, the
same arithmetic everywhere) at `PREC` significant digits, then rounded once to the nearest
double, so every platform returns the same bits. The sim never calls `math.exp`, `math.log`,
`math.log10`, `math.log2`, `math.sin`, `math.asinh`, `statistics.NormalDist` or a float `**`
(tests/unit/test_m35a_dmath.py scans for them); `math.sqrt`, `+ - * /`, `floor` and `fsum` are
exact IEEE operations and stay.

Correct rounding also means a result can differ from glibc's (whose `exp` misrounds about one
input in a thousand): the fixtures that moved are recorded in CHANGELOG (M35a).

Results are memoised: the sim calls these with the same few rates and exponents every month.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_EVEN, Context, Decimal
from functools import lru_cache
from typing import Final

PREC: Final = 40  # tunable-exempt: significant digits before the one rounding to a double
_CTX: Final = Context(prec=PREC, rounding=ROUND_HALF_EVEN, Emax=10**6, Emin=-(10**6))
_WIDE: Final = Context(prec=PREC + 20, rounding=ROUND_HALF_EVEN, Emax=10**6, Emin=-(10**6))
_CACHE: Final = 1 << 16  # tunable-exempt: memo entries per function
_EXP_MAX: Final = 709.782712893384  # tunable-exempt: exp above this overflows a double
_PI: Final = Decimal("3.14159265358979323846264338327950288419716939937510582097494")
_LN2: Final = _WIDE.ln(Decimal(2))
_TWO_PI: Final = _WIDE.multiply(_PI, 2)
_SMALL: Final = Decimal("1e-5")  # tunable-exempt: below it asinh's series is exact to 40 digits


def _float(d: Decimal) -> float:
    """The nearest double (float(str) rounds correctly, the same on every platform)."""
    return float(d)


@lru_cache(maxsize=_CACHE)
def exp(x: float) -> float:
    if not math.isfinite(x) or x > _EXP_MAX:
        return math.exp(x)  # inf, nan and overflow: IEEE's answers (or OverflowError)
    return _float(_CTX.exp(Decimal(x)))


@lru_cache(maxsize=_CACHE)
def log(x: float) -> float:
    if not math.isfinite(x) or x <= 0:
        return math.log(x)  # inf, nan, and ValueError for x <= 0
    return _float(_CTX.ln(Decimal(x)))


@lru_cache(maxsize=_CACHE)
def log10(x: float) -> float:
    """Exact for powers of ten, as `floor(log10(x))` needs."""
    if not math.isfinite(x) or x <= 0:
        return math.log10(x)
    return _float(_CTX.log10(Decimal(x)))


@lru_cache(maxsize=_CACHE)
def log2(x: float) -> float:
    """Exact for powers of two."""
    if not math.isfinite(x) or x <= 0:
        return math.log2(x)
    mantissa, power = math.frexp(x)
    if mantissa == 0.5:
        return float(power - 1)
    return _float(_CTX.divide(_WIDE.ln(Decimal(x)), _LN2))


@lru_cache(maxsize=_CACHE)
def asinh(x: float) -> float:
    if not math.isfinite(x) or x == 0:
        return math.asinh(x)
    d = Decimal(x).copy_abs()  # exact: abs() would round to the thread's context
    if d < _SMALL:  # the series: ln(1 + tiny) would lose x in the working precision
        sq = _WIDE.multiply(d, d)
        # x (1 - x^2/6 + 3x^4/40 - 15x^6/336), every step in this module's own context
        poly = _WIDE.fma(sq, _WIDE.divide(-15, 336), _WIDE.divide(3, 40))
        poly = _WIDE.fma(sq, _WIDE.fma(sq, poly, _WIDE.divide(-1, 6)), 1)
        out = _WIDE.multiply(d, poly)
        return math.copysign(_float(_CTX.plus(out)), x)
    out = _WIDE.ln(_WIDE.add(d, _WIDE.sqrt(_WIDE.fma(d, d, 1))))
    return math.copysign(_float(_CTX.plus(out)), x)


@lru_cache(maxsize=_CACHE)
def sin(x: float) -> float:
    if not math.isfinite(x):
        return math.sin(x)
    d = _WIDE.remainder_near(Decimal(x), _TWO_PI)  # into [-pi, pi]
    term, total, n, sq = d, d, 1, _WIDE.multiply(d, d)
    while True:
        term = _WIDE.divide(_WIDE.multiply(_WIDE.minus(term), sq), (2 * n) * (2 * n + 1))
        if term.is_zero() or abs(term) < abs(total).scaleb(-(PREC + 15)):
            break
        total = _WIDE.add(total, term)
        n += 1
    return _float(_CTX.plus(total))


@lru_cache(maxsize=_CACHE)
def pow(x: float, y: float) -> float:
    """x ** y as a float. An integral y is a repeated product in `decimal` (a negative x
    allowed); otherwise x must be positive. 0, inf and nan follow IEEE (math.pow)."""
    fx, fy = float(x), float(y)
    if fx == 0 or fy == 0 or not math.isfinite(fx) or not math.isfinite(fy) or fx == 1:
        return math.pow(fx, fy)
    if fy.is_integer() and abs(fy) <= 10_000:  # tunable-exempt: a month count, not a rate
        out = _WIDE.power(Decimal(fx), int(fy))
    elif fx < 0:
        return math.pow(fx, fy)  # ValueError, as math.pow gives
    else:
        out = _WIDE.exp(_WIDE.multiply(Decimal(fy), _WIDE.ln(Decimal(fx))))
    result = _float(_CTX.plus(out))
    if math.isinf(result):
        raise OverflowError("math range error")
    return result


# Wichura's AS241 (Applied Statistics 37, 1988), the algorithm statistics.NormalDist.inv_cdf
# uses, with this module's log and sqrt: the standard normal's quantile.
_A = (
    3.387132872796366608,
    133.14166789178437745,
    1971.5909503065514427,
    13731.693765509461125,
    45921.953931549871457,
    67265.770927008700853,
    33430.575583588128105,
    2509.0809287301226727,
)
_B = (
    1.0,
    42.313330701600911252,
    687.1870074920579083,
    5394.1960214247511077,
    21213.794301586595867,
    39307.89580009271061,
    28729.085735721942674,
    5226.495278852545925,
)
_C = (
    1.42343711074968357734,
    4.6303378461565452959,
    5.7694972214606914055,
    3.64784832476320460504,
    1.27045825245236838258,
    0.24178072517745061177,
    0.0227238449892691845833,
    7.7454501427834140764e-4,
)
_D = (
    1.0,
    2.05319162663775882187,
    1.6763848301838038494,
    0.68976733498510000455,
    0.14810397642748007459,
    0.0151986665636164571966,
    5.475938084995344946e-4,
    1.05075007164441684324e-9,
)
_E = (
    6.6579046435011037772,
    5.4637849111641143699,
    1.7848265399172913358,
    0.29656057182850489123,
    0.026532189526576123093,
    0.0012426609473880784386,
    2.71155556874348757815e-5,
    2.01033439929228813265e-7,
)
_F = (
    1.0,
    0.59983220655588793769,
    0.13692988092273580531,
    0.0148753612908506148525,
    7.868691311456132591e-4,
    1.8463183175100546818e-5,
    1.4215117583164458887e-7,
    2.04426310338993978564e-15,
)


def _poly(coefs: tuple[float, ...], x: float) -> float:
    out = 0.0
    for c in reversed(coefs):
        out = out * x + c
    return out


@lru_cache(maxsize=_CACHE)
def normal_inv_cdf(p: float) -> float:
    """The z with P(Z <= z) = p for a standard normal, 0 < p < 1."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in the range 0.0 < p < 1.0")
    q = p - 0.5
    if abs(q) <= 0.425:
        r = 0.180625 - q * q
        return q * _poly(_A, r) / _poly(_B, r)
    r = p if q <= 0.0 else 1.0 - p
    r = math.sqrt(-log(r))
    if r <= 5.0:
        r -= 1.6
        x = _poly(_C, r) / _poly(_D, r)
    else:
        r -= 5.0
        x = _poly(_E, r) / _poly(_F, r)
    return -x if q < 0.0 else x
