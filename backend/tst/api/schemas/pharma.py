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


class RxRangeOut(BaseModel):
    lo: float
    hi: float


class RxIndicationOut(BaseModel):
    key: str
    label: str
    area: str
    area_label: str
    orphan: bool
    market_cents: int = Field(description="Branded sales a year, world, at the game's scale")
    prevalence_m: float = Field(description="People living with it (oncology: new cases), M")
    price_cents: int = Field(description="A branded therapy's US list price a patient-year (real)")


class RxRegulatorOut(BaseModel):
    key: str
    name: str
    region: str
    application: str
    standard: str = Field(description="Its standard review's months, as a range")
    priority: str | None = None


class RxReadoutOut(BaseModel):
    stage: str
    month: str
    success: bool
    shown: RxRangeOut = Field(description="The chance shown before it read out")
    observed: float = Field(description="Its observed efficacy score")
    design: str


class RxReviewOut(BaseModel):
    regulator: str
    regulator_name: str
    application: str
    filed: str
    status: Literal["review", "approved", "crl", "withdrawn"]
    priority: bool
    expected: str = Field(description="When a decision comes, as a range (never the draw)")
    adcom: str | None = Field(default=None, description="The committee's vote, once it met")
    decided: str | None = None


class RxExclusivityOut(BaseModel):
    region: str
    region_label: str
    ends: str | None = Field(description="The month exclusivity ends there (once approved)")
    ended: bool


class RxValueOut(BaseModel):
    to_approval: RxRangeOut = Field(description="Chance to approval from here, as a range")
    rnpv_lo_cents: int
    rnpv_hi_cents: int
    peak_lo_cents: int = Field(description="Peak sales a year at the estimate's range")
    peak_hi_cents: int
    cost_left_cents: int
    years_to_launch: float
    explain: str


class RxProgrammeOut(BaseModel):
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
    preclinical_months: int = Field(description="Its preclinical stage's planned months")
    preclinical_months_without_ai: int = Field(description="The same without AI discovery")
    origin: str
    efficacy: RxRangeOut = Field(description="The estimate's range (never the true value)")
    readouts: int
    next_stage: str | None = Field(description="The trial it can start next, if ready")
    next_chance: RxRangeOut | None = Field(description="That stage's chance, as a range")
    next_cost_cents: int | None = None
    next_months: int | None = None
    redesign_cost_cents: int | None = Field(default=None, description="After a failure")
    can_file: list[str] = Field(description="Regulators it can be filed with now")
    breakthrough: bool
    accelerated: bool
    orphan: bool
    partner: str | None = None
    history: list[RxReadoutOut]
    reviews: list[RxReviewOut]
    approvals: list[str] = Field(description="Where it is approved (regulator or region)")
    exclusivity: list[RxExclusivityOut]
    value: RxValueOut | None


class RxMonthPointOut(BaseModel):
    month: str
    revenue_cents: int
    us_cents: int
    patients: float


class RxHtaOut(BaseModel):
    region: str
    status: Literal["pending", "covered", "refused"]
    expected: str = Field(description="When it decides, as a range (never the draw)")


class RxDrugOut(BaseModel):
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
    hta: list[RxHtaOut]
    history: list[RxMonthPointOut]
    blocked: bool


class RxPlantOut(BaseModel):
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


class RxCmoOut(BaseModel):
    name: str
    region: str
    kinds: list[str]
    quality: str
    chosen_for: list[str]


class RxAssetOut(BaseModel):
    id: int
    name: str
    indication_label: str
    area: str
    modality: str
    stage: str
    efficacy: RxRangeOut = Field(description="The estimate from its readouts so far")
    upfront_cents: int
    milestones_cents: int
    royalty: float
    acquire_cents: int
    until: str


class RxDealOut(BaseModel):
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


class RxInspectionOut(BaseModel):
    regulator: str
    month: str
    finding: str
    until: str | None
    fine_cents: int


class RxRecallOut(BaseModel):
    programme: str
    month: str
    cost_cents: int


class RxRivalDrugOut(BaseModel):
    name: str
    indication_label: str
    approved: int
    loe_us: int


class RxRivalApprovalOut(BaseModel):
    name: str
    area: str
    modality: str
    month: str


class RxRivalOut(BaseModel):
    id: int
    name: str
    generics: bool
    year_cents: int = Field(description="Revenue over the last 12 months")
    drugs: list[RxRivalDrugOut]
    pipeline: list[str]
    approvals: list[RxRivalApprovalOut] = Field(description="Its approvals after 2025")


class RxRuleOut(BaseModel):
    year: int
    text: str


class RxFactOut(BaseModel):
    month: str
    text: str


class PharmaOut(BaseModel):
    engaged: bool
    ai_ready: bool
    discovery_slots: int
    in_discovery: int
    researchers: int
    indications: list[RxIndicationOut]
    modalities: list[str]
    designs: list[str]
    regulators: list[RxRegulatorOut]
    programmes: list[RxProgrammeOut]
    drugs: list[RxDrugOut]
    plants: list[RxPlantOut]
    cmos: list[RxCmoOut]
    assets: list[RxAssetOut]
    deals: list[RxDealOut]
    inspections: list[RxInspectionOut]
    recalls: list[RxRecallOut]
    rivals: list[RxRivalOut]
    rules: list[RxRuleOut]
    facts: list[RxFactOut]


# --- requests ------------------------------------------------------------------------------


class RxStartIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    indication: str
    modality: Literal["small_molecule", "biologic", "cell_and_gene"]
    ai: bool = False


class RxTrialIn(BaseModel):
    programme_id: int
    design: Literal["lean", "standard", "large"] = "standard"


class RxProgrammeIn(BaseModel):
    programme_id: int


class RxFileIn(BaseModel):
    programme_id: int
    regulator: str


class RxPriceIn(BaseModel):
    programme_id: int
    list_cents: int = Field(gt=0)
    support: float = Field(ge=0, le=2)


class RxPlantIn(BaseModel):
    kind: Literal["api", "biologics"]
    region: str


class RxPlantQualityIn(BaseModel):
    plant_id: int
    level: Literal["low", "standard", "high"]


class RxCmoIn(BaseModel):
    kind: Literal["api", "biologics"]
    cmo: str


class RxLicenseInIn(BaseModel):
    asset_id: int
    acquire: bool = False


class RxLicenseOutIn(BaseModel):
    programme_id: int
    rival_id: int
    co_develop: bool = False


class RxPlatformIn(BaseModel):
    rival_id: int


class PharmaActionOut(BaseModel):
    pharma: PharmaOut
    energy: EnergyOut
    unread_inbox: int
