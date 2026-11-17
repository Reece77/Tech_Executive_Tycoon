"""The Medical API (M41, docs/formulas.md 50.7): devices with their class, route and evidence,
submissions by region with their stages and review ranges, studies' designs and results once
read out, coverage decisions, adoption, inspections and recalls that happened, quality systems,
and rivals' public products and shares. Never a study, review, coverage, inspection or recall
draw, a submission's drawn month, or a seeded rule before it happens."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class HealthRegulatorOut(BaseModel):
    key: str
    name: str
    region: str
    region_label: str
    share: float = Field(description="Its part's share of the region's people")


class RouteOut(BaseModel):
    regulator: str
    regulator_name: str
    route: str
    label: str
    review: str = Field(description="The months a decision takes, as a range")
    review_months: int = Field(description="The range's top, for Explain")
    explain: str = Field(description="How the range is made (data, not a draw)")
    fee_cents: int
    status: Literal["not_filed", "review", "information_requested", "cleared", "refused"]
    filed: str | None = None
    decided: str | None = None
    months_in: int | None = Field(default=None, description="Months since filing while open")
    blocker: str | None = Field(default=None, description="Why it cannot be filed now")


class StudyOut(BaseModel):
    id: int
    kind: str
    patients: int
    started: str
    readout: str = Field(description="The planned readout month (its design)")
    cost_cents: int
    spent_cents: int
    status: Literal["running", "succeeded", "failed"]
    success_range: str | None = Field(description="While running: the chance as a range")
    explain: str


class RegionOut(BaseModel):
    region: str
    label: str
    cleared: str = Field(description="Who has cleared the device there")
    sells_share: float = Field(description="The share of demand it may win now (public rules)")
    coverage: Literal["none", "not_needed", "pending", "covered", "denied"]
    coverage_window: str | None
    adoption: float | None


class RecallOut(BaseModel):
    turn: str
    klass: str
    units: int
    cost_cents: int
    caught_early: bool


class DeviceOut(BaseModel):
    product_id: int
    name: str
    category: str
    category_label: str
    status: str
    quality: float
    use: str | None
    use_label: str | None
    us_class: str | None
    eu_class: str | None
    evidence: float
    pccp: bool
    training_cents: int
    surveillance: bool
    update_needed: bool = Field(description="SaMD: a change of intended use needs a new filing")
    routes: list[RouteOut]
    studies: list[StudyOut]
    regions: list[RegionOut]
    recalls: list[RecallOut]
    quality_level: str


class UseOut(BaseModel):
    key: str
    label: str
    us_class: str
    eu_class: str
    us_route: str


class SubcategoryOut(BaseModel):
    key: str
    label: str
    consumables_cents: int
    needs_coverage: bool
    clinicians: bool
    software: bool
    uses: list[UseOut]


class StudyKindOut(BaseModel):
    kind: str
    patients: list[int]
    months: list[int]


class QualityPlantOut(BaseModel):
    facility_id: int
    region: str
    level: str
    cents_month: int


class InspectionOut(BaseModel):
    turn: str
    regulator: str
    finding: str
    until: str | None
    fine_cents: int
    for_cause: bool


class RivalProductOut(BaseModel):
    company: str
    product: str
    category: str
    customers: float
    share: float


class DatedRuleOut(BaseModel):
    label: str
    at: str
    note: str
    source: str


class MedicalOut(BaseModel):
    regulators: list[HealthRegulatorOut]
    subcategories: list[SubcategoryOut]
    devices: list[DeviceOut]
    study_kinds: list[StudyKindOut]
    plants: list[QualityPlantOut]
    quality_levels: dict[str, int] = Field(description="A plant's monthly cost by level")
    inspections: list[InspectionOut]
    rivals: list[RivalProductOut]
    precedents: list[DatedRuleOut]


class DesignIn(BaseModel):
    product_id: int
    use: str
    pccp: bool = False


class SubmitIn(BaseModel):
    product_id: int
    regulator: str


class StudyIn(BaseModel):
    product_id: int
    kind: Literal["feasibility", "pivotal", "post_market"]
    patients: int | None = None


class CoverageIn(BaseModel):
    product_id: int
    region: str


class SupportIn(BaseModel):
    product_id: int
    training_cents: int = Field(ge=0)
    surveillance: bool


class PlantQualityIn(BaseModel):
    facility_id: int
    level: Literal["low", "standard", "high"]


class MedicalActionOut(BaseModel):
    medical: MedicalOut
    energy: EnergyOut
    unread_inbox: int
