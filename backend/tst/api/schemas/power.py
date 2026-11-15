"""The Power API (M32, docs/formulas.md 46.9): prices, carbon prices, queue waits as ranges, plant
types' published costs, the player's plants and contracts, emissions and outages that happened.
Never a plant's hidden overrun or true completion, an outage draw, or a seeded future price or
policy step."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class PowerRegionOut(BaseModel):
    region: str
    label: str
    grid_usd_mwh: float = Field(description="This month's grid price, $/MWh (2010 dollars)")
    carbon_usd_t: float = Field(description="This month's carbon price, $/t")
    intensity: float = Field(description="The grid's tCO2 a MWh")
    queue_lo_months: float = Field(description="The grid queue's wait, low end of the range")
    queue_hi_months: float
    outages_a_year: float = Field(description="Grid outages a year a site sees")
    demand_mwh: float = Field(description="Last month's metered energy")
    plant_mwh: float
    ppa_mwh: float
    grid_mwh: float
    exported_mwh: float
    peak_mw: float
    grid_cents: int = Field(description="Last month's energy at the grid price")
    net_cents: int = Field(description="Last month's energy cost after plants, PPAs and exports")
    scope1_tonnes: float
    scope2_tonnes: float
    cheapest_plant: str
    cheapest_usd_mwh: float


class PowerMonthOut(BaseModel):
    turn: int
    region: str
    demand_mwh: float
    plant_mwh: float
    ppa_mwh: float
    grid_mwh: float
    exported_mwh: float
    grid_cents: int
    net_cents: int
    scope1_tonnes: float
    scope2_tonnes: float
    outage: bool
    wafers_lost: float


class PlantMonthOut(BaseModel):
    turn: int
    output_mwh: float
    used_mwh: float
    exported_mwh: float
    curtailed_mwh: float
    fuel_cents: int
    om_cents: int
    carbon_cents: int
    grid_charge_cents: int
    export_cents: int
    displaced_cents: int
    tonnes: float
    offline: bool


class PowerPlantOut(BaseModel):
    facility_id: int
    name: str
    type: str
    type_label: str
    mw: float
    region: str
    region_label: str
    city: str | None
    site_id: int | None = Field(description="Behind the meter of this facility")
    site_name: str | None
    status: str = Field(description="building, waiting for the grid, live, or offline")
    estimate_cents: int = Field(description="The quoted capex")
    paid_cents: int = Field(description="Capex paid so far (an overrun shows as it is paid)")
    expected_turn: int = Field(description="The month it is expected to generate (it slips)")
    live_turn: int | None
    queue_lo_months: float | None
    queue_hi_months: float | None
    queued_months: int | None = Field(description="Months in the grid queue so far")
    capacity_factor: float
    mwh_year: float
    levelised_usd_mwh: float = Field(description="A new plant of this type here, $/MWh")
    intensity: float
    outage_until: int | None
    month: PlantMonthOut | None


class PpaOut(BaseModel):
    id: int
    region: str
    region_label: str
    producer: str
    producer_name: str
    mwh_month: float
    price_usd_mwh: float
    start_turn: int
    end_turn: int
    status: str
    used_mwh: float
    paid_cents: int


class QueueOut(BaseModel):
    id: int
    facility_id: int
    name: str
    kind: str
    region: str
    mw: float
    joined_turn: int
    lo_months: float
    hi_months: float
    connected_turn: int | None


class GridOutageOut(BaseModel):
    turn: int
    region: str
    region_label: str


class PlantTypeOut(BaseModel):
    key: str
    label: str
    capex_kw_usd: float = Field(description="This year's published $/kW (2010 dollars)")
    build_months: int
    available: bool = Field(description="An SMR only from its era")
    life_years: int
    intensity: float
    levelised: dict[str, float] = Field(description="Region -> a new plant's $/MWh")
    capacity_factor: dict[str, float]


class SellerOut(BaseModel):
    region: str
    key: str
    name: str
    forward_usd_mwh: float


class PowerScreenOut(BaseModel):
    unlocked: bool = Field(description="Owned plants (stage 4)")
    min_stage: int
    sizes_mw: list[float]
    ppa_years: list[int]
    take_or_pay: float
    regions: list[PowerRegionOut]
    history: list[PowerMonthOut]
    plants: list[PowerPlantOut]
    ppas: list[PpaOut]
    queue: list[QueueOut]
    outages: list[GridOutageOut]
    plant_types: list[PlantTypeOut]
    sellers: list[SellerOut]
    sites: list[SiteOptionOut] = Field(description="The company's data centres and fabs")
    scope1_year: float
    scope2_year: float


class SiteOptionOut(BaseModel):
    facility_id: int
    name: str
    kind: str
    region: str
    city: str | None
    mw: float


class PowerSiteOut(BaseModel):
    city: str
    label: str
    region: str
    region_label: str
    price_usd_mwh: float
    queue_lo_months: float | None
    queue_hi_months: float | None
    carbon_usd_t: float
    outages_a_year: float
    behind_meter: bool
    cheapest_plant: str
    cheapest_usd_mwh: float


class SitingOut(BaseModel):
    kind: str
    size: float = Field(description="The planned facility's capacity in its kind's unit")
    mw: float
    sites: list[PowerSiteOut]


class PlantQuoteOut(BaseModel):
    type: str
    label: str
    mw: float
    region: str
    capex_cents: int
    monthly_capex_cents: int
    build_months: int
    ready_turn: int
    capacity_factor: float
    mwh_year: float
    levelised_usd_mwh: float
    intensity: float
    behind_meter: bool
    queue_lo_months: float | None
    queue_hi_months: float | None
    allowed: bool
    reason: str | None


class PpaQuoteOut(BaseModel):
    region: str
    producer: str
    producer_name: str
    mwh_month: float
    years: int
    price_usd_mwh: float
    forward_usd_mwh: float
    start_turn: int
    end_turn: int
    monthly_cents: int
    minimum_cents: int


class BuildPlantIn(BaseModel):
    plant_type: str
    mw: float
    region: str
    city: str | None = None
    site_id: int | None = None


class SignPpaIn(BaseModel):
    region: str
    producer: str
    mwh_month: float
    years: int


class PowerActionOut(BaseModel):
    power: PowerScreenOut
    energy: EnergyOut
    unread_inbox: int


PowerScreenOut.model_rebuild()
