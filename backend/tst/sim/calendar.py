"""Turn <-> calendar conversion. Turn 0 = January 2010; one turn = one month (ADR-0006).

All time math in the sim goes through this module; the sim never uses `datetime`.

ADR-0024 (M50): a game may start before 2010. Earlier months are negative turns (January 2008
is turn -24), and a save records its start turn (`start_turn_of`). Data series begin at
`HISTORY_START_YEAR`, the earliest start year offered.

M50b: January 2000 (turn -120) is the earliest. A history read is floored at the latest start
year at or before it (`history_floor_year`, `history_floor_turn`): a read from January 2008 sees
nothing before 2008 and one from January 2010 nothing before 2010, so a 2008 and a 2010 game read
exactly what they read before earlier years were added; a 2000 game's series step at both.
"""

from __future__ import annotations

from typing import Final

from tst.sim.errors import InvalidDateError

TURN_ZERO: Final = (2010, 1)
MONTHS_PER_YEAR: Final = 12
# ADR-0024: the years a campaign may start in, earliest first. 2010 is turn 0; every data
# series covers HISTORY_START_YEAR onward without a gap (the loader checks).
START_YEARS: Final[tuple[int, ...]] = (2000, 2008, 2010)  # M50b: 2000
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


# M50b: a year-end series (telecom, media) reads January at the year before + 1/12, so the 2008
# world's first read is 2007.08 and its floor sits between December 2007 (2007.0) and it
END_YEAR_2008_READ: Final = 2007.04


def history_floor_year(
    at: float, boundary: float = FROM_2010_READ, boundary_2008: float | None = None
) -> int:
    """M50b: the latest start year whose boundary (`boundary`, shifted to that year, or
    `boundary_2008` for 2008) is at or before the fractional year `at`; the earliest start
    year before every boundary."""
    for year in reversed(START_YEARS[1:]):
        shifted = boundary - (TURN_ZERO[0] - year)
        if boundary_2008 is not None and year == START_YEARS[1]:
            shifted = boundary_2008
        if at >= shifted:
            return year
    return START_YEARS[0]


def world_year_of(year: int) -> int:
    """M50b: the start year whose world a game begun in `year` is built on: the latest offered
    start year at or before it (2008 for a 2008-2009 Sandbox or scenario, 2010 from 2010)."""
    return max((y for y in START_YEARS if y <= year), default=START_YEARS[0])


def history_floor_turn(turn: int) -> int:
    """M50b: the first month of the latest start year at or before `turn` (0, -24 or -120)."""
    for year in reversed(START_YEARS):
        first = (year - TURN_ZERO[0]) * MONTHS_PER_YEAR
        if turn >= first:
            return first
    return HISTORY_START_TURN


def from_2010[V](
    points: dict[int, V],
    at: float,
    boundary: float = FROM_2010_READ,
    boundary_2008: float | None = None,
) -> dict[int, V]:
    """ADR-0024 (M50): a year-keyed series read at `at` >= `boundary` (a month from January
    2010) without its 2008-2009 entries, so a 2010 game reads exactly what it read before they
    were added (interpolation and "the year before" reach back). M50b: likewise a read from
    January 2008 without the 2000-2007 entries; earlier reads see them all."""
    floor = history_floor_year(at, boundary, boundary_2008)
    if floor == START_YEARS[0] or not any(y >= floor for y in points):
        return points
    if all(y >= floor for y in points):
        return points
    return {y: v for y, v in points.items() if y >= floor}
