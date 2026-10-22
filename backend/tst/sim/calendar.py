"""Turn <-> calendar conversion. Turn 0 = January 2010; one turn = one month (ADR-0006).

All time math in the sim goes through this module; the sim never uses `datetime`.
"""

from __future__ import annotations

from typing import Final

from tst.sim.errors import InvalidDateError

TURN_ZERO: Final = (2010, 1)
MONTHS_PER_YEAR: Final = 12
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
