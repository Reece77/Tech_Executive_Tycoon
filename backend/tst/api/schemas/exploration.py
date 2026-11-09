"""Exploration screen schemas (M18, formulas.md 34.5): heat-map bands, licences, every estimate
as a range with its category, holes and their assays, feasibility ranges, permits and sales.
Never a deposit's true tonnage, grade, recovery or sensitivity, an empty block's emptiness
before it is tested, a permit's decision month, or a team's skill."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class GeoCommodityOut(BaseModel):
    key: str
    label: str
    grade_unit: str = Field(description="pct | ppm: how a grade is shown")


class GeoRegionOut(BaseModel):
    key: str
    label: str
    prospectivity: dict[str, float] = Field(
        description="0-1 per commodity: the region's public geology (34.1)"
    )
    basis: dict[str, str]
    licence_fee_cents: int
    permit_years_low: float
    permit_years_high: float
    survey_cost_cents: int
    hole_cost_low_cents: int
    hole_cost_high_cents: int


class GeoBlockOut(BaseModel):
    region: str
    index: int = Field(description="0-based; shown as index + 1")
    holder: str | None = Field(description="Who holds its licence: a supplier or a company")
    project_id: int | None = Field(description="The group's open project on it, if any")
    bands: dict[str, str] = Field(
        description="commodity -> low | medium | high from the group's latest desk study"
    )


class DeskStudyOut(BaseModel):
    id: int
    company_id: int
    region: str
    commodity: str
    start_turn: int
    done_turn: int
    done: bool


class DrillHoleOut(BaseModel):
    n: int
    turn: int
    assay: float = Field(description="The hole's grade, a fraction of ore (public once drilled)")
    cost_cents: int


class EstimateRangeOut(BaseModel):
    low: float
    mid: float
    high: float
    pct: float = Field(description="The half-width shown as +/- this share of the midpoint")


class StageOptionOut(BaseModel):
    stage: str
    cost_cents: int
    months: int
    allowed: bool
    reason: str = ""


class ExplorationProjectOut(BaseModel):
    id: int
    company_id: int
    company: str
    region: str
    block: int
    label: str
    status: str = Field(description="active | permitted | refused | sold | relinquished | lapsed")
    commodity: str | None
    stage: str | None = Field(description="The stage running now")
    stage_due_turn: int | None
    holes_left: int
    licence_turn: int
    expires_turn: int
    renewals: int
    renewable: bool
    spent_cents: int
    reading: str | None = Field(description="Survey: none | weak | strong")
    deposit_chance_low: float | None = Field(
        default=None, description="The stated chance of a deposit under this reading"
    )
    deposit_chance_high: float | None = None
    kind: str | None = Field(description="hard_rock | brine | placer, as the survey reads it")
    sample_grade: EstimateRangeOut | None
    holes: list[DrillHoleOut]
    grade: EstimateRangeOut | None = Field(description="The running grade estimate from the holes")
    category: str | None = Field(description="inferred | indicated | measured")
    est_grade: EstimateRangeOut | None
    est_tonnage_mt: EstimateRangeOut | None
    level: str | None = Field(description="The latest feasibility study's level")
    capex_usd: EstimateRangeOut | None
    opex_usd_per_t: EstimateRangeOut | None
    recovery: EstimateRangeOut | None
    npv_low_cents: int | None
    npv_mid_cents: int | None
    npv_high_cents: int | None
    permit_start: int | None
    permit_years_low: float | None = Field(
        default=None, description="The region's typical years (never the decision month)"
    )
    permit_years_high: float | None = None
    protests: int
    protest_open: bool
    benefit_agreement: bool
    pushes: int
    permit_turn: int | None
    sale_quote_cents: int = Field(description="What a supplier would pay now (0: no buyer)")
    buyer: str | None
    sold_to: str | None
    sale_cents: int
    options: list[StageOptionOut]


class ExplorerOut(BaseModel):
    company_id: int
    name: str
    geologists: int
    busy: int = Field(description="Desk studies and geology stages running (one a geologist)")
    gate: list[str] = Field(description="What stands between it and exploring; empty: it may")


class ExplorationOut(BaseModel):
    turn: int
    confidence: float = Field(description="The stated confidence of every range")
    desk_cost_cents: int
    desk_months: int
    max_programme: int
    commodities: list[GeoCommodityOut]
    regions: list[GeoRegionOut]
    explorers: list[ExplorerOut]
    blocks: list[GeoBlockOut]
    desk_studies: list[DeskStudyOut]
    projects: list[ExplorationProjectOut]


class DeskStudyIn(BaseModel):
    region: str
    commodity: str
    company_id: int | None = None


class LicenceIn(BaseModel):
    region: str
    block: int = Field(ge=0)
    company_id: int | None = None


class StageIn(BaseModel):
    stage: Literal[
        "survey", "sampling", "estimate", "scoping", "pre_feasibility", "definitive", "permitting"
    ]
    commodity: str | None = None


class DrillIn(BaseModel):
    holes: int = Field(ge=1)


class ExplorationActionOut(BaseModel):
    exploration: ExplorationOut
    energy: EnergyOut
    unread_inbox: int
