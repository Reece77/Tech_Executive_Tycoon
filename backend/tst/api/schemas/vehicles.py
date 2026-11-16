"""The Vehicles API (M38, docs/formulas.md 49.7): EV shares, battery prices, subsidies and tariffs,
charging coverage, rivals' public line-ups and shares, approvals and recalls, and the player's
cars, cell plants and charging networks. Never an incident draw or chance, a region's drawn
S-curve speed, the learning rate, a cell plant's overrun, a seeded future rule or price before it
happens, or a rival's plans."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class YearValueOut(BaseModel):
    year: int
    value: float


class SubsidyOut(BaseModel):
    title: str
    country: str
    amount_cents: int = Field(description="A buyer's subsidy for an eligible car, 2010 cents")
    price_cap_cents: int | None
    rules: list[str] = Field(description="Sourcing and assembly rules running now")


class TariffOut(BaseModel):
    title: str
    origin: str
    market: str
    rate: float


class VehicleRegionOut(BaseModel):
    region: str
    label: str
    ev_share: float = Field(description="This month's electric share of new car sales")
    ev_share_history: list[YearValueOut]
    ev_sales_year: float = Field(description="EV sales a year at the game's scale, cars")
    car_sales_year: float = Field(description="New cars a year at the game's scale")
    public_chargers: float = Field(description="Public chargers, real world")
    coverage: float = Field(description="Charging coverage, 0-1")
    subsidies: list[SubsidyOut]
    tariffs: list[TariffOut]
    approved_levels: list[str]


class RivalShareOut(BaseModel):
    region: str
    share: float = Field(description="Its share of the region's EV buyers now")


class RivalCarOut(BaseModel):
    company_id: int
    company: str
    product: str
    quality: float
    price_cents: int | None
    launched: bool
    shares: list[RivalShareOut]


class CostLineOut(BaseModel):
    line: str
    cents: float


class ChemistryOut(BaseModel):
    key: str
    label: str
    wh_per_kg: float
    cost_mult: float
    range_mult: float


class CellMakerOut(BaseModel):
    key: str
    name: str
    country: str
    price_mult: float
    share: float


class BatteryOut(BaseModel):
    cell_cents: float = Field(description="This month's market price of a kWh of cells")
    pack_cents: float = Field(description="A kWh of pack (cells and integration)")
    history: list[YearValueOut] = Field(description="Cell price a kWh by year, to now")
    chemistries: list[ChemistryOut]
    cell_makers: list[CellMakerOut]


class VehicleSpecOut(BaseModel):
    pack_kwh: float
    chemistry: str
    charge_kw: float
    autonomy: str
    platform: str
    cells: str
    os_product_id: int | None


class LevelRegionOut(BaseModel):
    region: str
    level: str
    approved: list[str]


class EligibilityOut(BaseModel):
    region: str
    scheme: str
    amount_cents: int
    eligible: bool
    failed: list[str]


class CarMonthOut(BaseModel):
    turn: int
    units: float
    software_cents: int
    licence_cents: int
    unit_cost_cents: float


class MyCarOut(BaseModel):
    product_id: int
    name: str
    status: str
    spec: VehicleSpecOut
    range_km: float
    level: str = Field(description="The highest level its cars run in a region now")
    capable_level: str
    customers: float = Field(description="Cars on the road")
    units_last_month: float
    price_cents: int | None
    unit_cost: list[CostLineOut]
    unit_cost_cents: float
    software_cents_last_month: int
    software_share: float = Field(description="Software's share of the line's revenue to date")
    feature_points: float = Field(description="Range, charging, autonomy and platform points")
    levels: list[LevelRegionOut]
    eligibility: list[EligibilityOut]
    history: list[CarMonthOut]


class CellPlantOut(BaseModel):
    facility_id: int
    name: str
    region: str
    chemistry: str
    capacity_mwh: int
    status: str
    ready: str
    estimate_cents: int = Field(description="The quote at the order")
    capex_paid_cents: int
    yield_rate: float
    made_kwh: float
    to_group_kwh: float
    to_spot_kwh: float
    unit_cents: float = Field(description="Its cost a kWh last month")
    market_cents: float
    staff: int
    staff_needed: int


class VehiclePlantOut(BaseModel):
    facility_id: int
    name: str
    region: str
    capacity: int
    status: str
    ready: str
    yield_rate: float
    run_units: float


class ChargingOut(BaseModel):
    facility_id: int
    name: str
    region: str
    chargers: int
    status: str
    exclusive: bool
    kwh_sold: float
    revenue_cents: int
    energy_cents: int
    use: float


class IncidentOut(BaseModel):
    turn: int
    when: str
    product: str
    region: str
    level: str
    cars_recalled: float
    cost_cents: int


class LevelOptionOut(BaseModel):
    key: str
    label: str
    lead: float
    ai_quality: float
    features: float
    needs_approval: bool


class VehicleOptionsOut(BaseModel):
    chemistries: list[str]
    platforms: list[str]
    levels: list[LevelOptionOut]
    cell_sources: list[str]
    cell_plant_sizes: list[int]
    charging_sizes: list[int]
    vehicle_plant_sizes: list[int]
    pack_kwh: list[float]
    charge_kw: list[float]
    cell_plant_stage: int
    autonomy_lead: float = Field(description="Your lead in the autonomy domain")


class VehiclesScreenOut(BaseModel):
    turn: int
    in_history: bool = Field(description="True to December 2025: shares and rivals follow history")
    scale_note: str
    regions: list[VehicleRegionOut]
    battery: BatteryOut
    rivals: list[RivalCarOut]
    cars: list[MyCarOut]
    vehicle_plants: list[VehiclePlantOut]
    cell_plants: list[CellPlantOut]
    charging: list[ChargingOut]
    incidents: list[IncidentOut]
    options: VehicleOptionsOut


class SetVehicleSpecIn(BaseModel):
    pack_kwh: float
    chemistry: str
    charge_kw: float
    autonomy: str
    platform: str
    cells: str
    os_product_id: int | None = None


class BuildCellPlantIn(BaseModel):
    region: str
    capacity: int
    chemistry: str
    city: str | None = None


class BuildChargingIn(BaseModel):
    region: str
    chargers: int
    exclusive: bool = False
    city: str | None = None


class ChargingAccessIn(BaseModel):
    exclusive: bool


class VehiclesActionOut(BaseModel):
    vehicles: VehiclesScreenOut
    energy: EnergyOut
    unread_inbox: int
