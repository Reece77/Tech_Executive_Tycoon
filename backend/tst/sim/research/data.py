"""Schemas for the R&D tree's data (docs/formulas.md 21, M11): `tech_frontier.yaml`,
`eras.yaml` and balance.yaml's `rnd` block. Model definitions only (ADR-0008); `tst.loader`
reads the files. Domains and eras are data, so v3 can add domains without code (ADR-0020).
"""

from __future__ import annotations

import bisect
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_KEY = r"^[a-z][a-z0-9_]*$"
_WEIGHT_TOLERANCE = 1e-6  # tunable-exempt: float tolerance for weights that sum to 1
JANUARY, DECEMBER = 1, 12  # tunable-exempt: calendar months
FIRST_WINDOW_YEAR = 2026  # tunable-exempt: future eras follow the 2010-2025 history (26.4)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _sums_to_one(values: list[float]) -> bool:
    return abs(sum(values) - 1) <= _WEIGHT_TOLERANCE


_KEYS: dict[int, tuple[dict[int, float], list[int]]] = {}  # id -> (the table, its sorted keys)


def sorted_years(table: dict[int, float]) -> list[int]:
    """A year table's keys, sorted once per table (M37: tables reach 2069, read every month).
    The table is kept with its keys, so its id cannot be reused while cached; tables are
    loaded data, never changed."""
    hit = _KEYS.get(id(table))
    if hit is None or hit[0] is not table:
        hit = _KEYS[id(table)] = (table, sorted(table))
    return hit[1]


def latest_year(table: dict[int, float], year: int) -> int | None:
    """The latest key at or before `year`, or None if the table starts after it."""
    keys = sorted_years(table)
    i = bisect.bisect_right(keys, year)
    return keys[i - 1] if i else None


def rate_in(table: dict[int, float], year: int) -> float:
    """The latest entry at or before `year` (the first one before the table starts)."""
    key = latest_year(table, year)
    return table[sorted_years(table)[0] if key is None else key]


# --- balance.yaml: rnd ------------------------------------------------------------------------


class LicenseBalance(_Frozen):
    """Licensing (21.5)."""

    energy: int = Field(ge=0)
    margin: float = Field(ge=0)  # points the licensor stays ahead
    price_per_point_cents: int = Field(gt=0)
    price_arr_cents: int = Field(gt=0)  # the licensee's ARR that doubles the price
    royalty_bp: int = Field(ge=0)
    royalty_months: int = Field(gt=0)


class LeakBalance(_Frozen):
    """A researcher who leaves for a rival takes some of the lead (21.5)."""

    share: float = Field(ge=0, le=1)
    cap: float = Field(ge=0)


class RivalResearchBalance(_Frozen):
    """Incumbents' research action (21.6)."""

    rate: float = Field(ge=0)  # lead a month = rate x builder_skill / 10
    need_span: float = Field(gt=0)  # lead gap points for need 1
    era_bonus: float = Field(ge=0)  # need added when an era in the domain is near
    era_window_months: int = Field(ge=0)
    months: int = Field(gt=0)  # how long one research action runs
    pool_cost: float = Field(ge=0)  # builder pool growth while it runs
    weights: dict[str, float]  # by personality


class RevealBalance(_Frozen):
    """How exactly the player sees a rival's lead (21.7)."""

    range: float = Field(ge=0)
    licensed_range: float = Field(ge=0)


class RndBalance(_Frozen):
    """R&D tree and era milestones (formulas.md 21, M11)."""

    decay: float = Field(ge=0, lt=1)
    cap_per_point: float = Field(ge=0)
    cap_points: float = Field(ge=0)
    feature_per_point: float = Field(ge=0)
    feature_points: float = Field(ge=0)
    rate: float = Field(gt=0)
    half: float = Field(gt=0)
    start_energy: int = Field(ge=0)
    stop_energy: int = Field(ge=0)
    budget_energy: int = Field(ge=0)
    breakthrough_chance: float = Field(ge=0, le=1)
    breakthrough_points: float = Field(ge=0)
    dead_end_chance: float = Field(ge=0, le=1)
    dead_end_share: float = Field(ge=0, le=1)
    progress_window: int = Field(gt=0)
    quality_skill: float = Field(gt=0)
    quality_clamp: tuple[float, float]
    era_lead: float = Field(ge=0)
    era_baseline: float = Field(ge=0)
    first_mover_months: int = Field(ge=0)
    first_mover_cap: float = Field(ge=0)
    first_mover_brand: float = Field(ge=0)
    first_mover_appeal: float = Field(ge=1)  # M13b (27.3)
    license: LicenseBalance
    leak: LeakBalance
    rival: RivalResearchBalance
    reveal: RevealBalance


# --- tech_frontier.yaml ---------------------------------------------------------------------


class Baseline(_Frozen):
    start: float = Field(ge=0)
    per_year: dict[int, float] = Field(min_length=1)


class DomainDef(_Frozen):
    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
    baseline: Baseline
    research_skill: dict[str, float] = Field(min_length=1)
    budget_cents: int = Field(ge=0)
    compute_indexed: bool = False

    @model_validator(mode="after")
    def _check(self) -> DomainDef:
        if any(w < 0 for w in self.research_skill.values()) or not _sums_to_one(
            list(self.research_skill.values())
        ):
            raise ValueError(f"domain {self.key!r}: research_skill must be >= 0 and sum to 1")
        return self


class TechFrontierFile(_Frozen):
    domains: tuple[DomainDef, ...] = Field(min_length=1)
    tech_weights: dict[str, dict[str, float]]

    @model_validator(mode="after")
    def _check(self) -> TechFrontierFile:
        keys = [d.key for d in self.domains]
        if len(set(keys)) != len(keys):
            raise ValueError("tech_frontier.yaml: domain keys listed twice")
        for category, weights in self.tech_weights.items():
            if set(weights) - set(keys):
                raise ValueError(f"tech_weights.{category}: unknown domains")
            if any(w < 0 for w in weights.values()) or not _sums_to_one(list(weights.values())):
                raise ValueError(f"tech_weights.{category}: weights must be >= 0 and sum to 1")
        return self


# --- eras.yaml --------------------------------------------------------------------------------


class EraBoost(_Frozen):
    category: str
    segments: tuple[str, ...] | None = None  # None: every segment of the category
    growth: float = 0.0  # annual growth points added
    adoption: float = Field(default=1.0, gt=0)  # multiplier on adoption
    months: int = Field(gt=0)
    # M12b (26.4): quality-cap points for the category's products while it runs; with
    # own_chip only for companies using their own chip of the category's type
    cap_points: float = Field(default=0.0, ge=0)
    own_chip: bool = False

    def covers(self, category: str, segment: str) -> bool:
        return self.category == category and (self.segments is None or segment in self.segments)


class EraDef(_Frozen):
    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
    domain: str
    # (year, month 1-12): a historical era's arrival (YAML `arrival`; read it as `arrival`)
    historical: tuple[int, int] | None = Field(default=None, alias="arrival")
    # M12b (26.4): a future era's public window, ((y1, m1), (y2, m2)), instead of arrival
    window: tuple[tuple[int, int], tuple[int, int]] | None = None
    yield_cap: float | None = Field(default=None, gt=0, le=1)  # M12b: chips' yield cap
    boosts: tuple[EraBoost, ...] = ()
    # M50b (60.5): a history era's categories, which open for sale when it arrives
    opens: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> EraDef:
        if (self.historical is None) == (self.window is None):
            raise ValueError(f"era {self.key!r}: needs exactly one of arrival and window")
        months = [self.historical] if self.historical is not None else list(self.window or ())
        if any(not JANUARY <= m[1] <= DECEMBER for m in months):
            raise ValueError(f"era {self.key!r}: months must be 1-12")
        if self.window is not None:
            start, end = self.window
            if start[0] < FIRST_WINDOW_YEAR:
                raise ValueError(f"era {self.key!r}: a window may not start before 2026")
            if (end[0], end[1]) < (start[0], start[1]):
                raise ValueError(f"era {self.key!r}: a window must end after it starts")
        return self

    @property
    def windowed(self) -> bool:
        return self.window is not None

    @property
    def arrival(self) -> tuple[int, int]:
        """The public reference month as (year, month): the historical arrival, or a future
        era's window midpoint (26.4). Migration 0028 reads this for saves made before M11."""
        if self.historical is not None:
            return self.historical
        assert self.window is not None
        (y1, m1), (y2, m2) = self.window
        start = y1 * DECEMBER + m1 - 1
        n = y2 * DECEMBER + m2 - 1 - start + 1
        mid = start + n // 2
        return (mid // DECEMBER, mid % DECEMBER + 1)

    @property
    def categories(self) -> tuple[str, ...]:
        """Categories the era boosts, in boost order (the first mover's window, 21.4)."""
        return tuple(dict.fromkeys(b.category for b in self.boosts))


# M50b: a history era arrives by January 2008, so the 2008 world (and 2010's) has it from the start
HISTORY_ERA_LAST: Final = (2008, 1)  # tunable-exempt: the 2008 world's first month
BEYOND_FIRST, BEYOND_LAST = 2070, 2120  # tunable-exempt: 66.3's window years for the third wave


class ErasFile(_Frozen):
    eras: tuple[EraDef, ...] = ()
    base_growth: dict[str, dict[int, float]] = Field(default_factory=dict)
    # M52 (66.3): the third wave, windows 2070-2120 (sandbox past 2069); the loader appends it
    # to `eras` after every other era, so no earlier era's index (its stream key) moves
    beyond_2069: tuple[EraDef, ...] = ()
    # M50b (60.5): eras before the 2008 world (public cloud, social networks, ...), each opening
    # categories. Played only in a world begun before an era's month (a 2000 game); kept apart
    # from `eras`, so no era index, baseline, boost or estimate of a 2008 or 2010 game moves.
    history_eras: tuple[EraDef, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> ErasFile:
        keys = [e.key for e in (*self.eras, *self.beyond_2069, *self.history_eras)]
        if len(set(keys)) != len(keys):
            raise ValueError("eras.yaml: era keys listed twice")
        for e in self.beyond_2069:
            if e.window is None or e.window[0][0] < BEYOND_FIRST or e.window[1][0] > BEYOND_LAST:
                raise ValueError(
                    f"eras.yaml beyond_2069: {e.key!r} needs a window within"
                    f" {BEYOND_FIRST}-{BEYOND_LAST}"
                )
        for e in self.history_eras:
            if e.historical is None or e.historical > HISTORY_ERA_LAST or not e.opens or e.boosts:
                raise ValueError(
                    f"eras.yaml history_eras: {e.key!r} needs an arrival by "
                    f"{HISTORY_ERA_LAST[0]}-{HISTORY_ERA_LAST[1]:02d}, categories it opens and "
                    "no boosts"
                )
        for e in (*self.eras, *self.beyond_2069):
            if e.opens:
                raise ValueError(f"eras.yaml: {e.key!r}: only a history era opens categories")
        for category, table in self.base_growth.items():
            if not table or any(g < 0 for g in table.values()):
                raise ValueError(f"base_growth.{category}: needs entries, each >= 0")
        return self


type Domain = str
type ResearchStatus = Literal["active", "stopped"]
