"""Refineries screen schemas (M20, formulas.md 36): each plant's inputs, outputs, yield, power
cost, unit cost against market and margin; recipes, goods, contracts, power by region and the
group's value chain. Never a plant's true capex (its hidden overrun) beyond what has been paid,
or its staff's skill."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class RefineryMonthOut(BaseModel):
    turn: int
    output: float
    capacity: float = Field(description="What it could make this month with all its input")
    yield_: float = Field(alias="yield")
    input_group: float
    input_contract: float
    input_spot: float
    input_short: float
    input_cents: int
    power_cents: int
    power_index: float
    other_cents: int
    fixed_cents: int
    depreciation_cents: int
    staff_cents: int
    to_group: float
    to_contract: float
    to_spot: float
    revenue_cents: int
    market_cents: float = Field(description="The output's market price, cents a unit")
    unit_cost_cents: float
    margin: float | None = Field(description="Operating margin at market price")

    model_config = {"populate_by_name": True}


class RefineryHistoryOut(BaseModel):
    turn: int
    label: str
    output: float
    unit_cost_cents: float
    market_cents: float


class RefineryPlantOut(BaseModel):
    id: int
    company_id: int
    company: str
    name: str
    recipe: str
    recipe_label: str
    kind: str
    kind_label: str
    region: str
    region_label: str
    status: str = Field(description="building | live | closed")
    capacity: int
    unit: str
    output_unit: str = Field(description="The output good's volume unit")
    input_good: str | None
    input_label: str | None
    output_good: str
    output_label: str
    ready_turn: int
    ready_label: str
    estimate_cents: int = Field(description="The quoted capex")
    capex_paid_cents: int = Field(description="Capex paid so far (an overrun shows here)")
    book_value_cents: int
    staff: int
    staff_needed: int
    coverage: float
    unit_id: int | None
    stated_yield: float
    semi_grade: bool
    curbed_until: str | None
    curb_run: float | None
    stopped_until: str | None
    incident_open: bool
    incidents: int
    host_id: int | None
    month: RefineryMonthOut | None
    history: list[RefineryHistoryOut]


class RecipeOut(BaseModel):
    key: str
    label: str
    kind: str
    kind_label: str
    unit: str
    sizes: list[int]
    input_good: str | None
    input_label: str | None
    input_per_output: float
    output_good: str
    output_label: str
    output_unit: str
    yield_: float = Field(alias="yield")
    mwh_per_unit: float
    build_months: int
    life_months: int
    ramp_months: int
    staff_per: float
    capex_per_unit_cents: int = Field(description="Quoted capex per capacity unit this month")
    semi_grade: bool
    curbs: bool
    incident_rate: float

    model_config = {"populate_by_name": True}


class RefiningGoodOut(BaseModel):
    key: str
    label: str
    unit: str
    price_cents: float
    allocation: float


class RefiningDealOut(BaseModel):
    id: int
    company_id: int
    side: str
    good: str
    good_label: str
    unit: str
    signed_turn: int
    end_label: str
    monthly_volume: float
    price_cents: float
    taken: float
    last_taken: float
    charged_cents: int
    status: str


class OwnSupplyOut(BaseModel):
    facility_id: int
    seller: str
    buyer: str
    good: str
    good_label: str
    product: str | None
    volume: float
    taken: float
    unit_cents: float
    market_cents: float


class ChainLinkOut(BaseModel):
    stage: str = Field(description="mine | refinery | wafer | chip | device")
    company: str
    name: str
    detail: str
    supplies: list[str] = Field(description="Names of the links it feeds")


class RefiningPowerOut(BaseModel):
    region: str
    label: str
    index: float


class RefineriesOut(BaseModel):
    plants: list[RefineryPlantOut]
    recipes: list[RecipeOut]
    goods: list[RefiningGoodOut]
    deals: list[RefiningDealOut]
    supply: list[OwnSupplyOut]
    chain: list[ChainLinkOut]
    power: list[RefiningPowerOut]
    process_level: float = Field(description="The player company's process level (36.3)")
    semi_min_level: float
    deal_months_low: int
    deal_months_high: int
    build_energy: int
    deal_energy: int


class RefineryQuoteOut(BaseModel):
    recipe: str
    region: str
    capacity: int
    capex_cents: int = Field(description="The estimate; the true cost may run over")
    monthly_capex_cents: int
    build_months: int
    staff_needed: int
    power_index: float
    yield_: float = Field(alias="yield")
    input_cents: float
    power_cents: float
    other_cents: float
    fixed_cents: float
    depreciation_cents: float
    unit_cost_cents: float = Field(description="A unit at full output now, before staff")
    market_cents: float
    margin: float

    model_config = {"populate_by_name": True}


class BuildRefineryIn(BaseModel):
    recipe: str
    region: str
    capacity: int
    host_id: int | None = None
    city: str | None = None
    company_id: int | None = None


class RefiningDealIn(BaseModel):
    side: str = Field(description="buy | sell")
    good: str
    months: int
    volume: float = Field(description="Volume units a month")


class StaffRefineryIn(BaseModel):
    unit_id: int | None


class RefineriesActionOut(BaseModel):
    refineries: RefineriesOut
    energy: EnergyOut
    unread_inbox: int
