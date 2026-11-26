"""Every data series covers the earliest start year offered (ADR-0024 decision 4, M50).

The loader runs `coverage_problems` over each parsed data file before validation. A *series*
is a mapping keyed by calendar years (`{2010: ..., 2011: ...}`), a mapping keyed by months
(`{"2010-01": ...}`) or a list of `[month, value...]` rows. A series that reaches back to
January 2010 (turn 0) must also reach back to `calendar.HISTORY_START_YEAR` without a gap:

- its first entry is in or before that year (January of it, for a month-keyed series);
- an annual series (one listing both 2010 and 2011) lists every year from it to 2010.

A series that starts after 2010 (a product launched in 2017, a plan from 2027) is a later
fact of the world and needs nothing earlier.

Demand growth before 2010 has one source, each category's `early_growth` in categories.yaml
(checked by the loader for every category), so `growth_by_year` and eras.yaml's `base_growth`
(which start in 2010 and replace `growth` from then) are not series for this check.
"""

from __future__ import annotations

import re
from typing import Any, Final

from tst.sim.calendar import HISTORY_START_YEAR, TURN_ZERO

MONTH_KEY: Final = re.compile(r"^(19|20)\d\d-\d\d$")
YEAR_RANGE: Final = (1900, 2200)  # tunable-exempt: what counts as a calendar-year key
ZERO_YEAR: Final = TURN_ZERO[0]
# path suffixes read only from 2010 (see the module docstring)
EXEMPT: Final = (".growth_by_year", "eras.yaml.base_growth")


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


def _year_problem(path: str, years: list[int]) -> str | None:
    first = min(years)
    if first > ZERO_YEAR:
        return None  # starts after 2010: a later fact
    if first > HISTORY_START_YEAR:
        return f"{path} starts in {first}; it needs entries from {HISTORY_START_YEAR}"
    if ZERO_YEAR in years and ZERO_YEAR + 1 in years:  # an annual series: no gap allowed
        missing = [y for y in range(HISTORY_START_YEAR, ZERO_YEAR) if y not in years]
        if missing:
            return f"{path} has no entry for {missing}"
    return None


def _month_problem(path: str, months: list[str]) -> str | None:
    first = min(months)
    if first > f"{ZERO_YEAR}-01":
        return None
    if first > f"{HISTORY_START_YEAR}-01":
        return f"{path} starts in {first}; it needs entries from {HISTORY_START_YEAR}-01"
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
