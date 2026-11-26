"""Turn <-> calendar conversion. Turn 0 = January 2010; one turn = one month (ADR-0006).

All time math in the sim goes through this module; the sim never uses `datetime`.

ADR-0024 (M50): a game may start before 2010. Earlier months are negative turns (January 2008
is turn -24), and a save records its start turn (`start_turn_of`). Data series begin at
`HISTORY_START_YEAR`, the earliest start year offered.
"""

from __future__ import annotations

from typing import Final

from tst.sim.errors import InvalidDateError

TURN_ZERO: Final = (2010, 1)
MONTHS_PER_YEAR: Final = 12
# ADR-0024: the years a campaign may start in, earliest first. 2010 is turn 0; every data
# series covers HISTORY_START_YEAR onward without a gap (the loader checks).
START_YEARS: Final = (2008, 2010)
HISTORY_START_YEAR: Final = START_YEARS[0]
MONTH_ABBR: Final = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def turn_to_ym(turn: int) -> tuple[int, int]:
    """Return (year, month) for a turn. Negative turns are dates before January 2010."""
    year_offset, month_index = divmod(turn, MONTHS_PER_YEAR)
    return TURN_ZERO[0] + year_offset, TURN_ZERO[1] + month_index


def ym_to_turn(year: int, month: int) -> int:
    if not 1 <= month <= MONTHS_PER_YEAR:
        raise InvalidDateError(f"month must be 1..12, got {month}")
    return (year - TURN_ZERO[0]) * MONTHS_PER_YEAR + (month - TURN_ZERO[1])


def format_turn(turn: int) -> str:
    """Return a label such as "Jan 2010"."""
    year, month = turn_to_ym(turn)
    return f"{MONTH_ABBR[month - 1]} {year}"


def age_at(turn: int, birth_turn: int) -> int:
    """Age in whole years at `turn` (formulas.md section 0)."""
    return (turn - birth_turn) // MONTHS_PER_YEAR


def start_turn_of(year: int) -> int:
    """The start turn of a campaign begun in January of `year` (ADR-0024): 0 for 2010."""
    if year not in START_YEARS:
        raise InvalidDateError(f"a game starts in {', '.join(map(str, START_YEARS))}, not {year}")
    return ym_to_turn(year, 1)


HISTORY_START_TURN: Final = (HISTORY_START_YEAR - TURN_ZERO[0]) * MONTHS_PER_YEAR
# A series read at a fractional year at or after this reads as a 2010 game always has: the
# mid-year convention (vehicles, robotics, space) puts January 2010 at 2009.54 and December
# 2009 at 2009.46, so the boundary sits between them.
FROM_2010_READ: Final = TURN_ZERO[0] - 0.5


def from_2010[V](points: dict[int, V], at: float, boundary: float = FROM_2010_READ) -> dict[int, V]:
    """ADR-0024 (M50): a year-keyed series read at `at` >= `boundary` (a month from January
    2010) without its 2008-2009 entries, so a 2010 game reads exactly what it read before they
    were added (interpolation and "the year before" reach back). Earlier reads see them all."""
    if at < boundary or not any(y >= TURN_ZERO[0] for y in points):
        return points
    if all(y >= TURN_ZERO[0] for y in points):
        return points
    return {y: v for y, v in points.items() if y >= TURN_ZERO[0]}
