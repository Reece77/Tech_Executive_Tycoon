"""The Pharma API (M42, docs/formulas.md 55.7): programmes with their stage, design, readouts
once read out, efficacy and safety as ranges, the next stage's chance as a range, filings and
reviews' ranges, approvals and exclusivity dates, Explain's chance to approval and rNPV ranges;
marketed drugs' prices, patients, revenue and the IRA; plants, contract manufacturers,
inspections and recalls; assets for licence and deals; rivals' public drugs, pipelines and
approvals; dated rules that have happened. Never a molecule's true efficacy or safety, a
readout's draw before it reads out, a review's drawn month, or a seeded rule before it happens."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class RangeOut(BaseModel):
    lo: float
    hi: float


class IndicationOut(BaseModel):
    key: str
    label: str
    area: str
    area_label: str
    orphan: bool
    market_cents: int = Field(description="Branded sales a year, world, at the game's scale")
    prevalence_m: float = Field(description="People living with it (oncology: new cases), M")
    price_cents: int = Field(description="A branded therapy's US list price a patient-year (real)")


class RegulatorOut(BaseModel):
    key: str
    name: str
    region: str
    application: str
    standard: str = Field(description="Its standard review's months, as a range")
    priority: str | None = None


class ReadoutOut(BaseModel):
    stage: str
    month: str
    success: bool
    shown: RangeOut = Field(description="The chance shown before it read out")
    observed: float = Field(description="Its observed efficacy score")
    design: str


class ReviewOut(BaseModel):
    regulator: str
    regulator_name: str
    application: str
    filed: str
    status: Literal["review", "approved", "crl", "withdrawn"]
    priority: bool
    expected: str = Field(description="When a decision comes, as a range (never the draw)")
    adcom: str | None = Field(default=None, description="The committee's vote, once it met")
    decided: str | None = None


class ExclusivityOut(BaseModel):
    region: str
    region_label: str
    ends: str | None = Field(description="The month exclusivity ends there (once approved)")
    ended: bool


class ValueOut(BaseModel):
    to_approval: RangeOut = Field(description="Chance to approval from here, as a range")
    rnpv_lo_cents: int
    rnpv_hi_cents: int
    peak_lo_cents: int = Field(description="Peak sales a year at the estimate's range")
    peak_hi_cents: int
    cost_left_cents: int
    years_to_launch: float
    explain: str


class ProgrammeOut(BaseModel):
    id: int
    company: str
    name: str
    indication: str
    indication_label: str
    area: str
    modality: str
    stage: str
    status: str
    design: str
    patients: int
    started: str
    planned_end: str = Field(description="The stage's planned end (its design)")
    cost_cents: int
    spent_cents: int
    ai: bool
    origin: str
    efficacy: RangeOut = Field(description="The estimate's range (never the true value)")
    readouts: int
    next_stage: str | None = Field(description="The trial it can start next, if ready")
    next_chance: RangeOut | None = Field(description="That stage's chance, as a range")
    next_cost_cents: int | None = None
    next_months: int | None = None
    redesign_cost_cents: int | None = Field(default=None, description="After a failure")
    can_file: list[str] = Field(description="Regulators it can be filed with now")
    breakthrough: bool
    accelerated: bool
    orphan: bool
    partner: str | None = None
    history: list[ReadoutOut]
    reviews: list[ReviewOut]
    approvals: list[str] = Field(description="Where it is approved (regulator or region)")
    exclusivity: list[ExclusivityOut]
    value: ValueOut | None


class MonthPointOut(BaseModel):
    month: str
    revenue_cents: int
    us_cents: int
    patients: float


class HtaOut(BaseModel):
    region: str
    status: Literal["pending", "covered", "refused"]
    expected: str = Field(description="When it decides, as a range (never the draw)")


class DrugOut(BaseModel):
    programme_id: int
    name: str
    indication_label: str
    modality: str
    list_cents: int = Field(description="US list price a patient-year (real cents)")
    reference_cents: int = Field(description="The indication's branded reference price")
    support: float
    patients: float = Field(description="Real patients last month")
    revenue_cents: int = Field(description="Last month's revenue (game cents)")
    year_cents: int = Field(description="The last 12 months' revenue")
    generic: bool = Field(description="Exclusivity has ended somewhere it sells")
    ira: str | None = Field(default=None, description="The Medicare negotiation, once selected")
    hta: list[HtaOut]
    history: list[MonthPointOut]
    blocked: bool


class PlantOut(BaseModel):
    id: int
    kind: str
    label: str
    region: str
    ordered: str
    ready: str
    live: bool
    quality: str
    capex_cents: int
    patient_years_k: float = Field(description="Real thousand patient-years a year it makes")


class CmoOut(BaseModel):
    name: str
    region: str
    kinds: list[str]
    quality: str
    chosen_for: list[str]


class AssetOut(BaseModel):
    id: int
    name: str
    indication_label: str
    area: str
    modality: str
    stage: str
    efficacy: RangeOut = Field(description="The estimate from its readouts so far")
    upfront_cents: int
    milestones_cents: int
    royalty: float
    acquire_cents: int
    until: str


class DealOut(BaseModel):
    id: int
    kind: str
    counterparty: str
    programme: str | None
    signed: str
    upfront_cents: int
    milestones_cents: int
    royalty: float
    fee_cents: int
    until: str | None


class InspectionOut(BaseModel):
    regulator: str
    month: str
    finding: str
    until: str | None
    fine_cents: int


class RecallOut(BaseModel):
    programme: str
    month: str
    cost_cents: int


class RivalDrugOut(BaseModel):
    name: str
    indication_label: str
    approved: int
    loe_us: int


class RivalApprovalOut(BaseModel):
    name: str
    area: str
    modality: str
    month: str


class RivalOut(BaseModel):
    id: int
    name: str
    generics: bool
    year_cents: int = Field(description="Revenue over the last 12 months")
    drugs: list[RivalDrugOut]
    pipeline: list[str]
    approvals: list[RivalApprovalOut] = Field(description="Its approvals after 2025")


class RuleOut(BaseModel):
    year: int
    text: str


class FactOut(BaseModel):
    month: str
    text: str


class PharmaOut(BaseModel):
    engaged: bool
    ai_ready: bool
    discovery_slots: int
    in_discovery: int
    researchers: int
    indications: list[IndicationOut]
    modalities: list[str]
    designs: list[str]
    regulators: list[RegulatorOut]
    programmes: list[ProgrammeOut]
    drugs: list[DrugOut]
    plants: list[PlantOut]
    cmos: list[CmoOut]
    assets: list[AssetOut]
    deals: list[DealOut]
    inspections: list[InspectionOut]
    recalls: list[RecallOut]
    rivals: list[RivalOut]
    rules: list[RuleOut]
    facts: list[FactOut]


# --- requests ------------------------------------------------------------------------------


class StartIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    indication: str
    modality: Literal["small_molecule", "biologic", "cell_and_gene"]
    ai: bool = False


class TrialIn(BaseModel):
    programme_id: int
    design: Literal["lean", "standard", "large"] = "standard"


class ProgrammeIn(BaseModel):
    programme_id: int


class FileIn(BaseModel):
    programme_id: int
    regulator: str


class PriceIn(BaseModel):
    programme_id: int
    list_cents: int = Field(gt=0)
    support: float = Field(ge=0, le=2)


class PlantIn(BaseModel):
    kind: Literal["api", "biologics"]
    region: str


class PlantQualityIn(BaseModel):
    plant_id: int
    level: Literal["low", "standard", "high"]


class CmoIn(BaseModel):
    kind: Literal["api", "biologics"]
    cmo: str


class LicenseInIn(BaseModel):
    asset_id: int
    acquire: bool = False


class LicenseOutIn(BaseModel):
    programme_id: int
    rival_id: int
    co_develop: bool = False


class PlatformIn(BaseModel):
    rival_id: int


class PharmaActionOut(BaseModel):
    pharma: PharmaOut
    energy: EnergyOut
    unread_inbox: int
