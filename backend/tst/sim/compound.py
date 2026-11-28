"""Monthly compounding of drawn yearly rates, in time proportional to the years (M60).

Several markets grow from a start month by a rate drawn each January, compounded month by month:

    out = initial
    for turn in range(start, now + 1):
        out *= pow(1 + rate(year of turn), 1 / 12)

That loop cost one step a month since the start, called for every market and region every month,
so a 2100 game paid about 900 steps a call. `compounded` returns the same float: it does the same
multiplications in the same order, but keeps the value at the end of each completed year, keyed
by the initial value, the start month and every completed year's rate (so a rate drawn later, or
a different game, never reuses another's value). Only the current year's months are multiplied
on each call; a new year costs one year of steps once.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from tst.sim import dmath
from tst.sim.calendar import turn_to_ym

MONTHS: Final = 12  # tunable-exempt: months a year
_KEPT: dict[tuple[object, ...], float] = {}
_KEPT_MAX: Final = 1 << 16  # tunable-exempt: kept year-end values before the memo is cleared


def monthly_factor(rate: float) -> float:
    return float(dmath.pow(1.0 + rate, 1.0 / MONTHS))


def _months_in(year: int, start: int) -> int:
    """Months of `year` from `start` on (the start's year is partial when it is not January)."""
    first_year, first_month = turn_to_ym(start)
    return MONTHS - first_month + 1 if year == first_year else MONTHS


def compounded(
    initial: float, start: int, turn: int, rate_of_year: Callable[[int], float], tag: object
) -> float:
    """`initial` compounded monthly from `start` to `turn` inclusive (module docstring).
    `tag` names the series (the market, region...) so equal rates of two series share nothing
    they should not; values are equal either way. Before `start` it is `initial`."""
    if turn < start:
        return initial
    first, _ = turn_to_ym(start)
    year, month = turn_to_ym(turn)
    rates = tuple(rate_of_year(y) for y in range(first, year + 1))
    # the year-end value after the completed years, from the longest kept prefix
    done = len(rates) - 1
    k = done
    base = initial
    while k > 0:
        hit = _KEPT.get((tag, initial, start, rates[:k]))
        if hit is not None:
            base = hit
            break
        k -= 1
    if len(_KEPT) >= _KEPT_MAX:
        _KEPT.clear()
    out = base
    for i in range(k, done):
        f = monthly_factor(rates[i])
        for _ in range(_months_in(first + i, start)):
            out *= f
        _KEPT[(tag, initial, start, rates[: i + 1])] = out
    f = monthly_factor(rates[done])
    _, first_month = turn_to_ym(start)
    months = month - first_month + 1 if year == first else month
    for _ in range(months):
        out *= f
    return out


def compounded_slow(
    initial: float, start: int, turn: int, rate_of_year: Callable[[int], float]
) -> float:
    """The loop `compounded` replaces, one step a month (its tests compare the two)."""
    out = initial
    for t in range(start, turn + 1):
        out *= monthly_factor(rate_of_year(turn_to_ym(t)[0]))
    return out
