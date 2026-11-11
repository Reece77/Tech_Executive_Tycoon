"""Mines screen schemas (M19, formulas.md 35). Never a mine's hidden overrun before the cost to
complete is revised, nor its deposit's true tonnage, grade or recovery (so never its true
reserves): reserves are the resource estimate's range less what has been mined, and grades are
the reconciled grades of months already mined."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class MiningCompanyOut(BaseModel):
    id: int
    name: str
    role: str = Field(description="operating | holding | subsidiary")
    region: str | None
    cash_cents: int


class MineMonthOut(BaseModel):
    turn: int
    label: str
    output_t: float
    grade: float = Field(description="The month's reconciled grade (public once mined)")
    price_usd_t: float
    cost_usd_t: float = Field(description="Cash cost a t: operations, royalties and sustaining")
    revenue_cents: int
    margin_cents: int


class MineDealOut(BaseModel):
    id: int
    kind: str
    buyer: str
    signed_label: str
    end_label: str
    volume_t_year: float
    floor_usd_t: float
    ceiling_usd_t: float
    delivered_t: float
    running: bool


class MineOut(BaseModel):
    id: int
    name: str
    company_id: int
    company_name: str
    project_id: int
    region: str
    region_label: str
    commodity: str
    commodity_label: str
    subtype: str
    subtype_label: str
    status: str
    level: str = Field(description="The feasibility study it was built on")
    capacity_t: float = Field(description="Product a year at the design grade")
    ordered_label: str
    ready_label: str
    construction_months: int
    construction_done: int
    estimate_cents: int = Field(description="The study's capex for this capacity")
    overrun_low: float = Field(description="The study level's overrun range: public")
    overrun_high: float
    revised_cents: int | None = Field(
        description="The whole capex once the cost to complete is revised; None before"
    )
    capex_paid_cents: int
    book_cents: int
    reclamation_owed_cents: int
    reclamation_provisioned_cents: int
    product_t: float
    reserves_low_t: float | None = Field(
        description="The resource estimate's range of product left (est. ore less ore mined, at "
        "the design grade and recovery); never the truth"
    )
    reserves_high_t: float | None
    last_output_t: float | None
    last_grade: float | None
    design_grade: float
    price_usd_t: float
    price_usd_lb: float | None = Field(description="Copper's price a pound")
    cost_usd_t: float | None = Field(description="Last producing month's all-in cost a t")
    cost_usd_lb: float | None
    expected_cost_usd_t: float = Field(
        description="The all-in sustaining cost a t at capacity and the design grade"
    )
    staff: int
    staff_needed: int
    coverage: float
    unit_id: int | None
    safety: str
    buyer_id: int | None
    buyer_name: str | None
    price_kind: str
    margin: float | None
    state_share: float
    ban_until_label: str | None
    below_cost_months: int
    accidents: int
    open_event: str | None = Field(description="accident | takeover | crash awaiting an answer")
    arbitration_label: str | None
    closed_label: str | None
    close_reason: str | None
    history: list[MineMonthOut]
    deals: list[MineDealOut]


class MineQuoteOut(BaseModel):
    project_id: int
    label: str
    company_id: int
    company_name: str
    commodity: str
    commodity_label: str
    region: str
    subtype: str
    subtype_label: str
    level: str
    design_t: float
    capacity_low_t: float
    capacity_high_t: float
    estimate_cents: int = Field(description="At the design capacity")
    capex_scale: float
    construction_low: int
    construction_high: int
    overrun_low: float
    overrun_high: float
    staff_needed: int
    npv_low_cents: int | None
    npv_mid_cents: int | None
    npv_high_cents: int | None
    allowed: bool
    reason: str
    how: str = Field(description="How to unlock it when not allowed (M23c)")


class TransferAssetOut(BaseModel):
    kind: str = Field(description="project | facility")
    id: int
    label: str
    company_id: int
    company_name: str
    book_cents: int


class UnitOptionOut(BaseModel):
    id: int
    name: str
    company_name: str
    mining_engineers: int
    staffs: int | None = Field(description="The facility it staffs, if any")


class RivalBidOut(BaseModel):
    id: int
    bidder: str
    asset: str
    project_id: int | None
    mine_id: int | None
    cents: int
    expires_label: str


class RegionEventOut(BaseModel):
    turn: int
    label: str
    region: str
    region_label: str
    commodity: str | None
    kind: str
    months: int
    title: str
    seeded: bool


class RegionRiskOut(BaseModel):
    key: str
    label: str
    royalty_rate: float
    resource_nationalism: float


class RivalMinerOut(BaseModel):
    supplier: str
    name: str
    commodity: str
    commodity_label: str
    region: str
    region_label: str
    start_share: float
    capacity_share: float
    output_share: float


class MinesOut(BaseModel):
    turn_label: str
    group_stage: int
    found_min_stage: int
    found_how: str = Field(description="How founding a subsidiary opens (M23c)")
    found_min_cents: int
    found_energy: int
    build_energy: int
    companies: list[MiningCompanyOut]
    mines: list[MineOut]
    quotes: list[MineQuoteOut]
    assets: list[TransferAssetOut]
    units: list[UnitOptionOut]
    bids: list[RivalBidOut]
    events: list[RegionEventOut]
    regions: list[RegionRiskOut]
    rivals: list[RivalMinerOut]
    transfer_kinds: list[str]
    safety_levels: list[str]
    contract_months: list[int]
    offtake_years: list[int]


class MinesActionOut(BaseModel):
    mines: MinesOut
    energy: EnergyOut
    unread_inbox: int


class FoundSubsidiaryIn(BaseModel):
    name: str
    region: str
    cents: int


class TransferIn(BaseModel):
    to_company_id: int
    project_id: int | None = None
    facility_id: int | None = None


class BuildMineIn(BaseModel):
    project_id: int
    capacity_t: float | None = None


class MineSalesIn(BaseModel):
    buyer_id: int | None = None
    price_kind: str = "market"
    margin: float | None = None


class MineStaffIn(BaseModel):
    unit_id: int | None


class MineSafetyIn(BaseModel):
    safety: str


class MineSaleDealIn(BaseModel):
    deal_kind: str
    volume_t_year: float
    months: int | None = None
    years: int | None = None


class CareIn(BaseModel):
    restart: bool = False


class BidAnswerIn(BaseModel):
    accept: bool
