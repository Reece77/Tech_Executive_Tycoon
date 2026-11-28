"""Every data series covers the earliest start year offered (ADR-0024 decision 4, M50).

The loader runs `coverage_problems` over each parsed data file before validation. A *series*
is a mapping keyed by calendar years (`{2010: ..., 2011: ...}`), a mapping keyed by months
(`{"2010-01": ...}`) or a list of `[month, value...]` rows. A series that reaches back to
January 2010 (turn 0) must also reach back to `calendar.HISTORY_START_YEAR` without a gap:

- its first entry is in or before that year (January of it, for a month-keyed series);
- an annual series lists every year from its first to 2010, and a monthly series every month
  to January 2010 (M57r-A, review 10 item 28: a missing interior month or year passed). A series is
  annual (monthly) when most of its steps are one year (one month); a series written at anchor
  years and interpolated between is sparse and needs only its first entry.

A series that starts after 2010 (a product launched in 2017, a plan from 2027) is a later
fact of the world and needs nothing earlier.

Demand growth before 2010 has one source, each category's `early_growth` in categories.yaml
(checked by the loader for every category), so `growth_by_year` and eras.yaml's `base_growth`
(which start in 2010 and replace `growth` from then) are not series for this check.
"""

from __future__ import annotations

import re
from itertools import pairwise
from typing import Any, Final

from tst.sim.calendar import HISTORY_START_YEAR, TURN_ZERO

MONTH_KEY: Final = re.compile(r"^(19|20)\d\d-\d\d$")
YEAR_RANGE: Final = (1900, 2200)  # tunable-exempt: what counts as a calendar-year key
ZERO_YEAR: Final = TURN_ZERO[0]
# path suffixes read only from 2010 (see the module docstring)
# M50b: incumbents' `early_scale` is keyed by start year and `ipo_closed` lists windows: not series
EXEMPT: Final = (".growth_by_year", "eras.yaml.base_growth", ".early_scale", ".ipo_closed")


def _year_keys(node: dict[Any, Any]) -> list[int]:
    lo, hi = YEAR_RANGE
    return [k for k in node if isinstance(k, int) and not isinstance(k, bool) and lo <= k <= hi]


def _month_keys(node: dict[Any, Any]) -> list[str]:
    return [k for k in node if isinstance(k, str) and MONTH_KEY.match(k)]


def _month_rows(node: list[Any]) -> list[str] | None:
    if not node or not all(
        isinstance(r, list | tuple) and r and isinstance(r[0], str) and MONTH_KEY.match(r[0])
        for r in node
    ):
        return None
    return [r[0] for r in node]


DENSE_SHARE: Final = 0.75  # tunable-exempt: steps of one that make a series annual or monthly


def _dense(points: list[int]) -> bool:
    """Most of the sorted points' steps are one (an annual or monthly series, not anchors)."""
    xs = sorted(set(points))
    if len(xs) < 3:  # tunable-exempt: two points are anchors
        return False
    ones = sum(1 for a, b in pairwise(xs) if b - a == 1)
    return ones >= DENSE_SHARE * (len(xs) - 1)


def _gaps(points: list[int], last: int) -> list[int]:
    """The points missing from the first to `last` (the history: to January 2010)."""
    have = set(points)
    return [x for x in range(min(have), min(max(have), last) + 1) if x not in have]


def _year_problem(path: str, years: list[int]) -> str | None:
    first = min(years)
    if first > ZERO_YEAR:
        return None  # starts after 2010: a later fact
    if first > HISTORY_START_YEAR:
        return f"{path} starts in {first}; it needs entries from {HISTORY_START_YEAR}"
    annual = _dense(years) or (ZERO_YEAR in years and ZERO_YEAR + 1 in years)
    if annual and (missing := _gaps(years, ZERO_YEAR)):  # an annual series: no gap to 2010
        return f"{path} has no entry for {missing}"
    return None


def _month_index(key: str) -> int:
    return int(key[:4]) * 12 + int(key[5:7]) - 1  # tunable-exempt: months a year


def _month_problem(path: str, months: list[str]) -> str | None:
    first = min(months)
    if first > f"{ZERO_YEAR}-01":
        return None
    if first > f"{HISTORY_START_YEAR}-01":
        return f"{path} starts in {first}; it needs entries from {HISTORY_START_YEAR}-01"
    index = [_month_index(m) for m in months]
    if _dense(index) and (missing := _gaps(index, ZERO_YEAR * 12)):  # monthly: none to 2010-01
        shown = [f"{i // 12}-{i % 12 + 1:02d}" for i in missing[:3]]  # tunable-exempt: months
        return f"{path} has no entry for {shown}{' and more' if len(missing) > 3 else ''}"
    return None


def coverage_problems(node: Any, path: str) -> list[str]:
    """Each series under `node` that covers 2010 but not every year back to the earliest
    start year, as one message each."""
    out: list[str] = []
    if any(path.endswith(e) or f"{e}." in path for e in EXEMPT):
        return out
    if isinstance(node, dict):
        years = _year_keys(node)
        if years and len(years) * 2 >= len(node):
            problem = _year_problem(path, years)
            return [problem] if problem else []
        months = _month_keys(node)
        if months and len(months) * 2 >= len(node):
            problem = _month_problem(path, months)
            return [problem] if problem else []
        for key, value in node.items():
            out += coverage_problems(value, f"{path}.{key}")
    elif isinstance(node, list):
        rows = _month_rows(node)
        if rows is not None:
            problem = _month_problem(path, rows)
            return [problem] if problem else []
        for i, value in enumerate(node):
            label = value.get("key") or value.get("name") if isinstance(value, dict) else None
            out += coverage_problems(value, f"{path}[{label if label else i}]")
    return out
