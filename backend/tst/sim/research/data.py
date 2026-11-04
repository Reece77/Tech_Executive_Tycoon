"""Schemas for the R&D tree's data (docs/formulas.md 21, M11): `tech_frontier.yaml`,
`eras.yaml` and balance.yaml's `rnd` block. Model definitions only (ADR-0008); `tst.loader`
reads the files. Domains and eras are data, so v3 can add domains without code (ADR-0020).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_KEY = r"^[a-z][a-z0-9_]*$"
_WEIGHT_TOLERANCE = 1e-6  # tunable-exempt: float tolerance for weights that sum to 1
JANUARY, DECEMBER = 1, 12  # tunable-exempt: calendar months
FIRST_WINDOW_YEAR = 2026  # tunable-exempt: future eras follow the 2010-2025 history (26.4)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _sums_to_one(values: list[float]) -> bool:
    return abs(sum(values) - 1) <= _WEIGHT_TOLERANCE


def rate_in(table: dict[int, float], year: int) -> float:
    """The latest entry at or before `year` (the first one before the table starts)."""
    keys = sorted(table)
    rate = table[keys[0]]
    for start in keys:
        if start <= year:
            rate = table[start]
    return rate


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


class ErasFile(_Frozen):
    eras: tuple[EraDef, ...] = ()
    base_growth: dict[str, dict[int, float]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> ErasFile:
        keys = [e.key for e in self.eras]
        if len(set(keys)) != len(keys):
            raise ValueError("eras.yaml: era keys listed twice")
        for category, table in self.base_growth.items():
            if not table or any(g < 0 for g in table.values()):
                raise ValueError(f"base_growth.{category}: needs entries, each >= 0")
        return self


type Domain = str
type ResearchStatus = Literal["active", "stopped"]
