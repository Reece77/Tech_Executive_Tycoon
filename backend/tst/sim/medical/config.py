"""Schemas for M41's data and tunables (ADR-0008, docs/formulas.md 50): `medical.yaml` and
`medical.*` in balance.yaml.

Model definitions only (no file reads), so `tst.sim.data_models` can import them without a cycle.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import month_to_turn

type UsClass = Literal["I", "II", "III"]
type EuClass = Literal["I", "IIa", "IIb", "III"]
type StudyKind = Literal["feasibility", "pivotal", "post_market"]
type QualityLevel = Literal["low", "standard", "high"]
type RecallClass = Literal["I", "II", "III"]
type Finding = Literal["none", "observations", "warning_letter", "import_ban", "consent_decree"]

STUDY_KINDS: Final = ("feasibility", "pivotal", "post_market")
QUALITY_LEVELS: Final = ("low", "standard", "high")
RECALL_CLASSES: Final = ("I", "II", "III")
FINDINGS: Final = ("observations", "warning_letter", "import_ban", "consent_decree")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _range(r: tuple[int, int] | tuple[float, float], what: str) -> None:
    if r[0] > r[1] or r[0] < 0:
        raise ValueError(f"{what}: a range must be [lo, hi] with 0 <= lo <= hi")


# --- medical.yaml ---------------------------------------------------------------------------


class MarketSize(_Frozen):
    real_2024_b: float = Field(gt=0)  # real world revenue, USD billions
    real_2010_b: float = Field(gt=0)


class EuClasses(_Frozen):
    mdd: EuClass
    mdr: EuClass


class UseDef(_Frozen):
    """An intended use (50.2): its classes and whether a predicate exists in the US."""

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    us_class: dict[str, UsClass] = Field(min_length=1)  # "YYYY-MM" from -> class
    eu_class: EuClasses
    exempt: bool = False  # class I exempt from premarket review
    predicate_from: str | None = None  # the month a predicate exists (None: novel)
    pivotal: bool = False  # needs a successful pivotal study (PMA in the US)

    def us_class_at(self, turn: int) -> UsClass:
        out = None
        for month, klass in sorted(self.us_class.items(), key=lambda kv: month_to_turn(kv[0])):
            if month_to_turn(month) <= turn:
                out = klass
        if out is None:
            raise ValueError(f"use {self.key}: no class before turn {turn}")
        return out


class SubcategoryDef(_Frozen):
    key: str = Field(min_length=1)  # a categories.yaml key (family medical)
    label: str = Field(min_length=1)
    market: MarketSize
    consumables_cents: int = Field(ge=0)  # a month per installed unit
    consumables_cogs: float = Field(ge=0, le=1)
    needs_coverage: bool
    clinicians: bool
    software: bool = False
    uses: tuple[UseDef, ...] = Field(min_length=1)

    def use(self, key: str) -> UseDef:
        for u in self.uses:
            if u.key == key:
                return u
        raise KeyError(key)


class ReviewWindow(_Frozen):
    from_: str = Field(alias="from")
    months: tuple[int, int]

    @model_validator(mode="after")
    def _check(self) -> ReviewWindow:
        _range(self.months, "review months")
        return self


class MoreInfo(_Frozen):
    chance: float = Field(ge=0, le=1)
    months: tuple[int, int]


class RouteDef(_Frozen):
    """A route to market (50.2) at one health regulator."""

    key: str = Field(min_length=1)
    regulator: str = Field(min_length=1)
    label: str = Field(min_length=1)
    review: tuple[ReviewWindow, ...] = Field(min_length=1)
    more_info: MoreInfo
    approve: float = Field(gt=0, le=1)
    fee_cents: int = Field(ge=0)
    source: str = Field(min_length=1)
    needs_pivotal: bool = False
    from_: str | None = Field(default=None, alias="from")  # first month it is open
    until: str | None = None  # last month it is open
    class_iii_months: int = Field(default=0, ge=0)  # added for class III and implantables
    predicate_months: tuple[int, int] | None = None  # review with an approved equivalent

    def open_at(self, turn: int) -> bool:
        if self.from_ is not None and turn < month_to_turn(self.from_):
            return False
        return self.until is None or turn <= month_to_turn(self.until)

    def window(self, turn: int) -> tuple[int, int]:
        out = self.review[0].months
        for w in self.review:
            if month_to_turn(w.from_) <= turn:
                out = w.months
        return out


class RelianceDef(_Frozen):
    region: str
    relies_on: tuple[str, ...] = Field(min_length=1)  # health regulator keys, in order
    months: tuple[int, int]


class Dates(_Frozen):
    de_novo_direct: str
    mdr_applies: str
    mdd_legacy_until: dict[EuClass, str]
    pccp_from: str
    breakthrough_from: str
    tcet_from: str
    eu_hta_devices_from: str


class StudyKindDef(_Frozen):
    patients: tuple[int, int]
    months: tuple[int, int]
    evidence: float = Field(gt=0, le=1)  # evidence strength a success adds
    success: float = Field(gt=0, lt=1)  # base chance at standard quality


class StudiesDef(_Frozen):
    kinds: dict[StudyKind, StudyKindDef]
    cost_per_patient_cents: dict[str, int]
    de_novo_pivotal_patients: tuple[int, int]


class CoverageDef(_Frozen):
    region: str  # a regions.yaml key, or "other"
    label: str = Field(min_length=1)
    months: tuple[int, int]
    approve: tuple[float, float]  # with no evidence, with full evidence
    tcet_months: int | None = None


class QualityLevelDef(_Frozen):
    label: str = Field(min_length=1)
    cents_month: int = Field(ge=0)
    defect: float = Field(gt=0)
    inspection: float = Field(gt=0)


class QualityDef(_Frozen):
    levels: dict[QualityLevel, QualityLevelDef]
    contract_level: QualityLevel


class InspectionsDef(_Frozen):
    chance_year: float = Field(ge=0, le=1)
    outcomes: dict[str, float]


class RecallsDef(_Frozen):
    chance_year: float = Field(ge=0, le=1)
    classes: dict[RecallClass, float]
    cost_share: dict[RecallClass, float]


class PrecedentDef(_Frozen):
    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    at: str
    note: str = Field(min_length=1)
    source: str = Field(min_length=1)


class MedicalFile(_Frozen):
    """medical.yaml (50)."""

    history_end: str
    subcategories: tuple[SubcategoryDef, ...] = Field(min_length=1)
    routes: tuple[RouteDef, ...] = Field(min_length=1)
    reliance: tuple[RelianceDef, ...] = ()
    dates: Dates
    studies: StudiesDef
    coverage: tuple[CoverageDef, ...] = Field(min_length=1)
    quality: QualityDef
    inspections: InspectionsDef
    recalls: RecallsDef
    precedents: tuple[PrecedentDef, ...] = ()

    @property
    def history_end_turn(self) -> int:
        return month_to_turn(self.history_end)

    def subcategory(self, key: str) -> SubcategoryDef | None:
        return next((s for s in self.subcategories if s.key == key), None)

    def route(self, key: str) -> RouteDef:
        for r in self.routes:
            if r.key == key:
                return r
        raise KeyError(key)

    def coverage_in(self, region: str) -> CoverageDef:
        for c in self.coverage:
            if c.region == region:
                return c
        return next(c for c in self.coverage if c.region == "other")

    @model_validator(mode="after")
    def _check(self) -> MedicalFile:
        keys = [r.key for r in self.routes]
        if len(set(keys)) != len(keys):
            raise ValueError("medical.yaml: route keys must be unique")
        if not any(c.region == "other" for c in self.coverage):
            raise ValueError("medical.yaml: coverage needs an 'other' row")
        for s in self.subcategories:
            if s.key not in self.studies.cost_per_patient_cents:
                raise ValueError(f"medical.yaml: no study cost for {s.key}")
        for k in STUDY_KINDS:
            if k not in self.studies.kinds:
                raise ValueError(f"medical.yaml: studies.kinds needs {k}")
        if set(self.quality.levels) != set(QUALITY_LEVELS):
            raise ValueError("medical.yaml: quality.levels needs low, standard and high")
        if abs(sum(self.recalls.classes.values()) - 1) > 1e-6:  # tunable-exempt: tolerance
            raise ValueError("medical.yaml: recalls.classes must sum to 1")
        if set(self.inspections.outcomes) != set(FINDINGS):
            raise ValueError(f"medical.yaml: inspections.outcomes needs {FINDINGS}")
        return self


# --- balance.yaml medical.* -----------------------------------------------------------------


class StudyBalance(_Frozen):
    quality_weight: float = Field(ge=0)  # success chance a quality point above 50
    evidence_weight: float = Field(ge=0)  # success chance at full prior evidence
    bounds: tuple[float, float]  # the chance stays within these
    shown_band: float = Field(ge=0, le=1)  # half-width of the shown range
    redesign_months: int = Field(ge=0)
    redesign_cost_share: float = Field(ge=0)  # of the failed study's cost
    energy: int = Field(ge=0)


class ReviewBalance(_Frozen):
    quality_weight: float = Field(ge=0)  # approval chance a quality point above 50
    evidence_weight: float = Field(ge=0)  # approval chance at full evidence
    bounds: tuple[float, float]
    pccp_months: int = Field(ge=0)  # a change control plan adds to the review
    update_features: float = Field(gt=0)  # SaMD feature points past clearance that need a new file
    warning_hold_months: int = Field(ge=0)  # a warning letter holds new decisions there
    energy: int = Field(ge=0)


class CoverageBalance(_Frozen):
    no_coverage_share: float = Field(ge=0, le=1)  # 50.4: early adopters without coverage
    energy: int = Field(ge=0)


class AdoptionBalance(_Frozen):
    seed: float = Field(gt=0, lt=1)  # clinicians' adoption at clearance
    rate: float = Field(gt=0)  # monthly logistic rate at no evidence or training
    evidence_weight: float = Field(ge=0)  # the rate x (1 + this x evidence)
    training_weight: float = Field(ge=0)  # the rate x (1 + this x training / full)
    training_full_cents: int = Field(
        gt=0
    )  # a month's clinical education per region for full effect
    floor: float = Field(ge=0, le=1)  # demand share at no adoption
    recall_hit: float = Field(ge=0, le=1)  # adoption lost to a class I recall (x share)


class RecallBalance(_Frozen):
    surveillance_cents: int = Field(ge=0)  # a product's monthly post-market surveillance cost
    caught_early: float = Field(ge=0, le=1)  # chance surveillance catches a defect early
    install_weight: float = Field(ge=0)  # chance x (1 + this x log10 of installed units)
    block_months: dict[RecallClass, int]  # sales stopped after a recall
    brand_hit: dict[RecallClass, float]  # brand points lost
    lawsuit_share: float = Field(ge=0)  # class I: lawsuits cost this x the field action
    inspect_after_class_i: float = Field(ge=0, le=1)  # chance a class I recall brings an inspection


class InspectionBalance(_Frozen):
    import_ban_months: int = Field(ge=0)
    consent_decree_months: int = Field(ge=0)
    consent_fine_share: float = Field(ge=0, le=1)  # of the year's medical revenue
    warning_brand_hit: float = Field(ge=0)
    for_cause_mult: float = Field(ge=1)  # findings x this on a for-cause inspection


class DriftBalance(_Frozen):
    """Seeded rules after 2025 (50, stream medical family 4): review times drift by region."""

    sd: float = Field(ge=0)
    bounds: tuple[float, float]


class MedicalBalance(_Frozen):
    study: StudyBalance
    review: ReviewBalance
    coverage: CoverageBalance
    adoption: AdoptionBalance
    recall: RecallBalance
    inspection: InspectionBalance
    drift: DriftBalance
    quality_energy: int = Field(ge=0)
