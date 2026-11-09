"""Schema for M18's data (ADR-0008, docs/formulas.md 34): geology.yaml, and `geology.*` and
`exploration.*` in balance.yaml. Model definitions only (no imports from the rest of the sim),
so `tst.sim.data_models` can import them without a cycle."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

KINDS: Final = ("hard_rock", "brine", "placer")  # 34.1 deposit types
LEVELS: Final = ("scoping", "pre_feasibility", "definitive")  # 34.2 feasibility levels
CATEGORIES: Final = ("inferred", "indicated", "measured")  # 34.2 resource categories
BANDS: Final = ("low", "medium", "high")  # 34.2 desk-study heat-map bands
READINGS: Final = ("none", "weak", "strong")  # 34.2 survey anomaly readings

type Kind = Literal["hard_rock", "brine", "placer"]
type Level = Literal["scoping", "pre_feasibility", "definitive"]
type Category = Literal["inferred", "indicated", "measured"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _weights(kinds: dict[str, float], where: str) -> dict[str, float]:
    bad = sorted(set(kinds) - set(KINDS))
    if bad:
        raise ValueError(f"{where}: unknown deposit kinds {bad}")
    if not kinds or any(w < 0 for w in kinds.values()) or sum(kinds.values()) <= 0:
        raise ValueError(f"{where}: kinds need non-negative weights with a positive total")
    return kinds


class GeoCommodity(_Frozen):
    """An explorable commodity's deposits (geology.yaml commodities)."""

    key: str
    label: str = Field(min_length=1)
    grade_unit: Literal["pct", "ppm"]
    kinds: dict[str, float]
    grade_median: float = Field(gt=0, lt=1)  # fraction of ore that is saleable product
    grade_sd: float = Field(ge=0)
    tonnage_median_mt: float = Field(gt=0)
    tonnage_sd: float = Field(ge=0)
    hole_sd: float = Field(gt=0)  # hole-to-hole log-sd of assays
    recovery: tuple[float, float]
    capex_per_tpy_usd: float = Field(gt=0)
    opex_per_t_usd: float = Field(gt=0)
    trace_grade: float = Field(gt=0, lt=1)

    @model_validator(mode="after")
    def _check(self) -> GeoCommodity:
        _weights(self.kinds, f"geology.yaml {self.key}")
        lo, hi = self.recovery
        if not 0 < lo <= hi <= 1:
            raise ValueError(f"geology.yaml {self.key}: recovery must be 0 < lo <= hi <= 1")
        if self.trace_grade >= self.grade_median:
            raise ValueError(f"geology.yaml {self.key}: trace_grade must be below grade_median")
        return self


class GeoRegion(_Frozen):
    """A region's ground (geology.yaml regions)."""

    prospectivity: dict[str, float]
    basis: dict[str, str]
    kinds: dict[str, dict[str, float]] = Field(default_factory=dict)
    licence_fee_cents: int = Field(gt=0)
    permit_years: tuple[float, float]
    cost_index: float = Field(gt=0)
    sensitivity: float = Field(ge=0, le=1)
    refusal: float = Field(ge=0, lt=1)

    @model_validator(mode="after")
    def _check(self) -> GeoRegion:
        if any(not 0 <= p <= 1 for p in self.prospectivity.values()):
            raise ValueError("geology.yaml: prospectivity must be in 0-1")
        if set(self.basis) != set(self.prospectivity):
            raise ValueError("geology.yaml: every prospectivity needs its basis")
        lo, hi = self.permit_years
        if not 0 < lo <= hi:
            raise ValueError("geology.yaml: permit_years must be 0 < lo <= hi")
        for key, kinds in self.kinds.items():
            _weights(kinds, f"geology.yaml kinds.{key}")
        return self


class GeologyFile(_Frozen):
    commodities: tuple[GeoCommodity, ...] = Field(min_length=1)
    regions: dict[str, GeoRegion]

    @model_validator(mode="after")
    def _check(self) -> GeologyFile:
        keys = [c.key for c in self.commodities]
        if len(set(keys)) != len(keys):
            raise ValueError("geology.yaml: duplicate commodity keys")
        for name, region in self.regions.items():
            missing = sorted(set(keys) - set(region.prospectivity))
            extra = sorted(set(region.prospectivity) - set(keys))
            if missing or extra:
                raise ValueError(
                    f"geology.yaml {name}: prospectivity missing {missing}, unknown {extra}"
                )
            if bad := sorted(set(region.kinds) - set(keys)):
                raise ValueError(f"geology.yaml {name}: kinds for unknown commodities {bad}")
        return self

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(c.key for c in self.commodities)

    def commodity(self, key: str) -> GeoCommodity:
        for c in self.commodities:
            if c.key == key:
                return c
        raise KeyError(key)

    def kinds_of(self, region: str, key: str) -> dict[str, float]:
        return self.regions[region].kinds.get(key) or self.commodity(key).kinds


# --- balance.yaml: geology.* -----------------------------------------------------------------


class GeologyBalance(_Frozen):
    blocks_per_region: int = Field(ge=1)
    deposit_rate: float = Field(ge=0, le=1)
    grade_scale: float = Field(gt=0)
    size_lift: float = Field(ge=0, le=2)
    depth_m: tuple[float, float]
    infra_km: tuple[float, float]
    difficulty_sd: float = Field(ge=0)
    sensitivity_sd: float = Field(ge=0)
    cells: int = Field(ge=41)  # more than the measured category's holes
    supplier_blocks: int = Field(ge=0)

    @model_validator(mode="after")
    def _check(self) -> GeologyBalance:
        for name, (lo, hi) in (("depth_m", self.depth_m), ("infra_km", self.infra_km)):
            if not 0 < lo <= hi:
                raise ValueError(f"geology.{name} must be 0 < lo <= hi")
        return self


# --- balance.yaml: exploration.* -------------------------------------------------------------


class DeskBalance(_Frozen):
    cost_cents: int = Field(ge=0)
    months: int = Field(ge=1)
    signal: float = Field(ge=0)
    noise_sd: float = Field(gt=0)
    high_share: float = Field(gt=0, lt=1)
    medium_share: float = Field(ge=0, lt=1)

    @model_validator(mode="after")
    def _check(self) -> DeskBalance:
        if self.high_share + self.medium_share >= 1:
            raise ValueError("exploration.desk: high_share + medium_share must be under 1")
        return self


class LicenceBalance(_Frozen):
    years: int = Field(ge=1)
    renewals: int = Field(ge=0)


class SurveyBalance(_Frozen):
    cost_cents: int = Field(ge=0)
    months: int = Field(ge=1)
    signal: float = Field(ge=0)
    size_weight: float = Field(ge=0)
    noise_sd: float = Field(gt=0)
    strong_at: float
    weak_at: float
    commodity_misread: float = Field(ge=0, le=1)
    bands: dict[str, tuple[float, float]]

    @model_validator(mode="after")
    def _check(self) -> SurveyBalance:
        if self.weak_at > self.strong_at:
            raise ValueError("exploration.survey: weak_at must not exceed strong_at")
        if sorted(self.bands) != sorted(READINGS):
            raise ValueError(f"exploration.survey.bands needs exactly {list(READINGS)}")
        return self


class SamplingBalance(_Frozen):
    cost_cents: int = Field(ge=0)
    months: int = Field(ge=1)
    range: float = Field(gt=0, lt=1)


class DrillBalance(_Frozen):
    hole_base_cents: int = Field(ge=0)
    hole_per_m_cents: int = Field(ge=0)
    holes_per_month: int = Field(ge=1)
    max_programme: int = Field(ge=1)


class EstimateBalance(_Frozen):
    cost_cents: int = Field(ge=0)
    months: int = Field(ge=1)
    inferred: int = Field(ge=2)
    indicated: int = Field(ge=2)
    measured: int = Field(ge=2)
    tonnage_sd: dict[str, float]

    @model_validator(mode="after")
    def _check(self) -> EstimateBalance:
        if not self.inferred < self.indicated < self.measured:
            raise ValueError("exploration.estimate: inferred < indicated < measured holes")
        if sorted(self.tonnage_sd) != sorted(CATEGORIES):
            raise ValueError(f"exploration.estimate.tonnage_sd needs {list(CATEGORIES)}")
        return self

    def holes_for(self, category: str) -> int:
        return {"inferred": self.inferred, "indicated": self.indicated}.get(category, self.measured)


class FeasibilityBalance(_Frozen):
    levels: tuple[str, ...]
    cost_cents: dict[str, int]
    months: dict[str, int]
    accuracy: dict[str, float]
    recovery_sd: dict[str, float]
    min_category: dict[str, str]
    life_years: int = Field(ge=1)
    build_years: dict[str, int]
    discount_rate: float = Field(gt=0, lt=1)
    royalty: float = Field(ge=0, lt=1)
    infra_capex_per_km: float = Field(ge=0)
    depth_capex_per_m: float = Field(ge=0)
    kind_capex: dict[str, float]
    kind_opex: dict[str, float]
    deck_years: int = Field(ge=0)

    @model_validator(mode="after")
    def _check(self) -> FeasibilityBalance:
        if tuple(self.levels) != LEVELS:
            raise ValueError(f"exploration.feasibility.levels must be {list(LEVELS)}")
        for name in ("cost_cents", "months", "accuracy", "recovery_sd", "min_category"):
            if sorted(getattr(self, name)) != sorted(LEVELS):
                raise ValueError(f"exploration.feasibility.{name} needs {list(LEVELS)}")
        if any(c not in CATEGORIES for c in self.min_category.values()):
            raise ValueError("exploration.feasibility.min_category: unknown category")
        for name in ("build_years", "kind_capex", "kind_opex"):
            if sorted(getattr(self, name)) != sorted(KINDS):
                raise ValueError(f"exploration.feasibility.{name} needs {list(KINDS)}")
        return self


class PermittingBalance(_Frozen):
    requires: Level
    benefit_odds: float = Field(ge=0, le=1)
    protest_rate: float = Field(ge=0, le=1)
    consult_cents: int = Field(ge=0)
    consult_months: int = Field(ge=0)
    benefit_cents: int = Field(ge=0)
    push_legal: float = Field(ge=0, le=1)
    push_delay_months: int = Field(ge=0)
    push_legal_cents: int = Field(ge=0)
    push_ruthless: float = Field(ge=0)
    refusal_on_push: float = Field(ge=0, le=1)


class MinorBalance(_Frozen):
    accident_rate: float = Field(ge=0, le=1)
    accident_fine_cents: int = Field(ge=0)
    bonanza_ratio: float = Field(gt=1)
    dry_streak: int = Field(ge=2)


class SaleBalance(_Frozen):
    share: dict[str, float]
    anomaly_cents: int = Field(ge=0)
    energy: int = Field(ge=0)


class ExplorationBalance(_Frozen):
    min_stage: int = Field(ge=0, le=5)
    confidence: float = Field(gt=0, lt=1)
    skill_base: float = Field(gt=0)
    skill_slope: float = Field(ge=0)
    skill_floor: float = Field(gt=0)
    geologist_role: str
    stages_per_geologist: int = Field(ge=1)
    energy: int = Field(ge=0)
    desk: DeskBalance
    licence: LicenceBalance
    survey: SurveyBalance
    sampling: SamplingBalance
    drill: DrillBalance
    estimate: EstimateBalance
    feasibility: FeasibilityBalance
    permitting: PermittingBalance
    minor: MinorBalance
    sale: SaleBalance
