"""The Robotics and Mobility API (M39, docs/formulas.md 53.5): robot markets by region, prices,
makers' public lines and shares, humanoid announcements and adoption once the era is public, the
player's robot lines and plant automation; robotaxi cities, rival services, the player's zones,
fleets, rides, utilisation and incidents that happened. Never an incident or approval draw, a
permit's decision month, a seeded window or growth path before it opens, or a rival's plans."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class YearPointOut(BaseModel):
    year: int
    value: float


class RobotRegionOut(BaseModel):
    region: str
    label: str
    installations_year: float = Field(description="Industrial robots installed a year, real world")
    game_installations_year: float = Field(description="The same at the game's scale")
    history: list[YearPointOut] = Field(description="Installations a year, real world, to now")
    density: float | None = Field(description="Robots per 10,000 manufacturing workers (latest)")
    labour_cents_hour: float = Field(description="Manufacturing labour cost an hour, 2010 cents")
    humanoid_adoption: float = Field(description="Share of the worker pool humanoids serve now")


class RobotShareOut(BaseModel):
    region: str
    share: float = Field(description="Its share of the region's served robot buyers now")


class RobotMakerOut(BaseModel):
    company_id: int
    company: str
    owner: str
    product: str
    category: str
    quality: float
    price_cents: int | None
    selling: bool
    shares: list[RobotShareOut]


class AnnouncementOut(BaseModel):
    month: str
    company: str
    label: str
    price_cents: int | None


class HumanoidMarketOut(BaseModel):
    era: str
    window: str = Field(description="The era's public window, e.g. 2030-2035")
    arrived: str | None = Field(description="The month it arrived; None before")
    open: bool
    homes_open: bool = Field(description="Whether humanoids sell to homes yet")
    actuator_index: float = Field(description="Actuators' cost over their first-year cost")
    actuator_cents: float = Field(description="A humanoid's actuators this month, 2010 cents")
    best_capability: float
    announcements: list[AnnouncementOut]


class RobotLineOut(BaseModel):
    product_id: int
    name: str
    category: str
    status: str
    quality: float
    capability: float | None = Field(description="A humanoid's capability, 0-100")
    ai: str | None
    chips: str | None
    customers: float
    unit_cost_cents: float


class AutomationMonthOut(BaseModel):
    month: str
    units: float
    saved_cents: int
    service_cents: int
    depreciation_cents: int
    level: float


class UnitCostOut(BaseModel):
    labour_cents: float
    fixed_cents: float
    depreciation_cents: float
    robots_cents: float
    total_cents: float


class PlantAutomationOut(BaseModel):
    facility_id: int
    name: str
    kind: str
    region: str
    capacity: int
    robots: int
    own_robots: int
    max_robots: int
    level: float = Field(description="Share of the plant's line labour robots replace")
    saving_cents: float = Field(description="Line labour saved a unit run")
    wage_cents_month: float = Field(description="A line worker's labour a month in the region")
    cost_without: UnitCostOut = Field(description="Conversion cost a unit at full use, no robots")
    cost_with: UnitCostOut = Field(description="The same with its robots")
    capex_cents: int
    book_cents: int
    month: AutomationMonthOut | None
    history: list[AutomationMonthOut]


class ProductOptionOut(BaseModel):
    product_id: int
    name: str
    quality: float


class RoboticsOptionsOut(BaseModel):
    robot_cents: float = Field(description="A bought robot's price, 2010 cents")
    system_cents: float = Field(description="A bought robot installed (integration included)")
    service_share: float = Field(description="A year's service over the robot's price")
    own_robot_lines: list[ProductOptionOut]
    ai_models: list[ProductOptionOut]
    accelerators: list[ProductOptionOut]
    max_robots: int
    target_level: float


class RoboticsScreenOut(BaseModel):
    month: str
    scale: float
    scale_basis: str
    regions: list[RobotRegionOut]
    makers: list[RobotMakerOut]
    humanoids: HumanoidMarketOut
    lines: list[RobotLineOut]
    plants: list[PlantAutomationOut]
    options: RoboticsOptionsOut


class RobotaxiCityOut(BaseModel):
    key: str
    label: str
    region: str
    l4_approved: bool = Field(description="The region's regulator allows driverless service")
    trips_month: float = Field(description="Ride-hailing trips a month at the game's scale")
    fare_cents: float = Field(description="A human ride-hail trip's fare, 2010 cents")
    acceptance: float = Field(description="Riders' robotaxi share of covered trips")
    first_service: str | None
    rival_fleet: float = Field(description="Rival robotaxis in the city, real cars")


class RivalServiceOut(BaseModel):
    operator: str
    city: str
    since: str
    running: bool
    fleet: float
    rides_week: float = Field(description="Paid rides a week, real world")


class HistoryIncidentOut(BaseModel):
    month: str
    operator: str
    city: str
    label: str


class ZoneMonthOut(BaseModel):
    month: str
    cars: int
    rides: float
    utilisation: float
    revenue_cents: int
    energy_cents: int
    cleaning_cents: int
    insurance_cents: int
    remote_cents: int
    depreciation_cents: int
    contribution_cents: int
    contribution_per_ride_cents: float | None
    rides_per_car_day: float


class ZoneOut(BaseModel):
    zone_id: int
    product_id: int
    service: str
    city: str
    city_label: str
    size: str
    status: str = Field(description="applied (under review), active, suspended, refused, closed")
    applied: str
    approved: str | None
    suspended_until: str | None
    cars: int
    car_source: str
    price_cents: int
    depot_cars: float = Field(description="Cars the company's depots in the city serve")
    breakeven_rides: float = Field(description="Rides a car a day at which a car breaks even")
    month: ZoneMonthOut | None
    history: list[ZoneMonthOut]


class DepotOut(BaseModel):
    facility_id: int
    name: str
    city: str
    capacity: int
    status: str
    ready: str


class RoboIncidentOut(BaseModel):
    month: str
    zone_id: int
    city: str
    serious: bool
    cost_cents: int
    suspended_until: str | None


class ServiceOut(BaseModel):
    product_id: int
    name: str
    status: str
    quality: float
    brand: float


class ZoneSizeOut(BaseModel):
    key: str
    share: float
    review_months: int


class MobilityOptionsOut(BaseModel):
    can_drive_l4: bool
    l4_lead: float
    l4_ai_quality: float
    zone_sizes: list[ZoneSizeOut]
    robotaxi_cents: float = Field(description="A bought robotaxi's price this month")
    own_car_lines: list[ProductOptionOut] = Field(description="Own car lines that drive at L4")
    depot_sizes: list[int]
    depot_capex_cents: float = Field(description="A depot's capex a car served, at index 1.0")
    max_cars: int


class MobilityScreenOut(BaseModel):
    month: str
    cities: list[RobotaxiCityOut]
    rivals: list[RivalServiceOut]
    history_incidents: list[HistoryIncidentOut]
    services: list[ServiceOut]
    zones: list[ZoneOut]
    depots: list[DepotOut]
    incidents: list[RoboIncidentOut]
    options: MobilityOptionsOut


class InstallRobotsIn(BaseModel):
    robots: int = Field(ge=1)
    product_id: int | None = Field(default=None, description="An own robot line; None buys")


class HumanoidSpecIn(BaseModel):
    ai_product_id: int | None = None
    chip_product_id: int | None = None


class OpenZoneIn(BaseModel):
    product_id: int
    city: str
    size: str
    price_cents: int = Field(default=0, ge=0, description="0: the city's human fare")


class AddCarsIn(BaseModel):
    cars: int = Field(ge=1)
    car_product_id: int | None = Field(default=None, description="An own L4 car line; None buys")


class RidePriceIn(BaseModel):
    price_cents: int = Field(ge=0)


class BuildDepotIn(BaseModel):
    city: str
    capacity: int


class RoboticsActionOut(BaseModel):
    robotics: RoboticsScreenOut
    energy: EnergyOut
    unread_inbox: int


class MobilityActionOut(BaseModel):
    mobility: MobilityScreenOut
    energy: EnergyOut
    unread_inbox: int
