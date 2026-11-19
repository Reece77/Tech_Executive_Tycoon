"""The Space API (M40, docs/formulas.md 56.5): launch vehicles, launches and their outcomes, cost
a kg, satellites, constellations and coverage, subscribers by region, licences, and rivals' public
launches and constellations. Never a launch-failure draw, a licence's decision month, the seeded
debris rule or rivals' growth before they happen, or a rival's plans."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class CostPerKgOut(BaseModel):
    vehicle: str
    company: str
    cost_per_kg_cents: float = Field(description="Its list price over its payload, 2010 cents")
    target: bool = Field(description="A stated aspiration, not a flown price")


class ProviderOut(BaseModel):
    company_id: int | None
    company: str
    launches_year: float = Field(description="Orbital launches a year (public), real world")


class WorldLaunchesOut(BaseModel):
    year: int
    launches: float


class ReuseLevelOut(BaseModel):
    key: str
    label: str
    lead: float = Field(description="Reusability lead points it needs")
    min_months: int = Field(description="Months of the programme it needs")
    reached: bool


class FlightCostOut(BaseModel):
    """Explain: a launch's cost (56.1)."""

    level: str
    build_cents: int = Field(description="The whole vehicle, built new")
    reused_share: float
    flights_per_vehicle: int
    refurb_share: float
    operations_cents: int
    flight_cents: int = Field(
        description="A flight: the expendable part, the reused part's share, refurbishment and"
        " operations"
    )
    payload_kg: float = Field(description="Payload flown at the level")
    cost_per_kg_cents: float
    expendable_per_kg_cents: float = Field(description="The same design flown expendable")


class VehicleOut(BaseModel):
    product_id: int
    name: str
    status: str
    quality: float
    payload_kg: float
    aim: str
    level: str = Field(description="The reuse level it flies at now")
    cost: FlightCostOut
    price_cents: int | None = Field(description="Its price to commercial operators")
    flights: int
    failures: int
    reliability: float | None = Field(
        description="Successful flights over flights, None before its first"
    )
    failure_rate_lo: float = Field(
        description="The model's failure chance range for its next flight"
    )
    failure_rate_hi: float
    grounded_until: str | None = Field(description="The month an investigation ends, if grounded")
    pads: float = Field(description="Launch-site pad units live")
    cadence: float = Field(description="Launches a month its sites can fly")


class LaunchOut(BaseModel):
    month: str
    vehicle: str
    purpose: str
    constellation: str | None
    satellites: int
    ok: bool
    insured_cents: int


class ShellOut(BaseModel):
    index: int
    label: str
    satellites: int
    size: int
    complete: bool
    regions: list[str]


class ConstellationMonthOut(BaseModel):
    month: str
    in_orbit: int
    subscribers: float
    revenue_cents: int
    spend_cents: int


class PaybackOut(BaseModel):
    """Explain: a constellation's payback (56.4 target 3)."""

    capex_cents: int = Field(
        description="Satellites and launches capitalized and in service or waiting"
    )
    cash_cents: int = Field(description="Cumulative cash flow since it was planned")
    last_year_cash_cents: int = Field(description="Cash flow over the last 12 months")
    months_to_payback: float | None = Field(
        description="At the last 12 months' rate; None if not earning"
    )
    paid_back: str | None


class ConstellationOut(BaseModel):
    id: int
    name: str
    kind: str
    product_id: int | None
    product: str | None
    shells: list[ShellOut]
    in_orbit: int
    ground: int
    planned: int
    lost: int
    mass_kg: float
    life_months: int
    d2d: bool
    insured: bool
    build_per_month: int
    launches_per_month: int
    vehicle_product_id: int | None
    satellite_cents: int = Field(description="A satellite's made cost this month")
    covered: list[str]
    capacity_gbps: float
    payback: PaybackOut
    history: list[ConstellationMonthOut]


class RegionServiceOut(BaseModel):
    region: str
    label: str
    covered: bool
    licence: str | None = Field(description="applied, granted or refused; None if never applied")
    subscribers: float
    serviceable: float = Field(description="Subscribers its constellations can serve there")
    d2d_subscribers: float


class BroadbandLineOut(BaseModel):
    product_id: int
    name: str
    status: str
    terminal_price_cents: int
    terminal_cost_cents: int = Field(description="A terminal's cost to make this month")
    d2d_partner: bool
    d2d_capable: bool
    regions: list[RegionServiceOut]


class SpaceLicenceOut(BaseModel):
    region: str
    label: str
    status: str
    applied: str
    granted: str | None


class RivalConstellationOut(BaseModel):
    name: str
    company: str
    kind: str
    satellites: float = Field(description="In orbit now (public), real world")
    subscribers: float | None = Field(description="Thousands (public, to 2025), real world")


class MilestoneOut(BaseModel):
    month: str
    label: str


class LineOptionOut(BaseModel):
    product_id: int
    name: str


class SpaceScreenOut(BaseModel):
    month: str
    open: bool = Field(description="Whether this game has space markets")
    reusability_lead: float
    programme_started: str | None
    reuse_levels: list[ReuseLevelOut]
    vehicles: list[VehicleOut]
    undesigned: list[LineOptionOut] = Field(description="Your launch lines with no design yet")
    eo_lines: list[LineOptionOut] = Field(description="Your Earth-observation lines")
    launches: list[LaunchOut]
    cost_per_kg: list[CostPerKgOut]
    world_launches: list[WorldLaunchesOut]
    providers: list[ProviderOut]
    milestones: list[MilestoneOut]
    constellations: list[ConstellationOut]
    broadband: list[BroadbandLineOut]
    licences: list[SpaceLicenceOut]
    rivals: list[RivalConstellationOut]
    d2d_open: str | None = Field(
        description="The month direct-to-device service opened, once it has"
    )
    debris_rule: str | None = Field(
        description="The month the tighter debris rule came, once it has"
    )
    site_regions: list[str]
    bought_launch_cents: int = Field(description="A bought launch's price this month")
    bought_payload_kg: float


class LaunchSpecIn(BaseModel):
    payload_kg: float
    reuse: str


class ConstellationIn(BaseModel):
    name: str
    kind: str
    product_id: int
    shells: int
    mass_kg: float
    life_months: int
    build_per_month: int
    launches_per_month: int
    vehicle_product_id: int | None = None
    d2d: bool = False
    insured: bool = True


class ConstellationPlanIn(BaseModel):
    shells: int
    build_per_month: int
    launches_per_month: int
    vehicle_product_id: int | None = None
    insured: bool = True


class SpaceLicenceIn(BaseModel):
    region: str


class TerminalPriceIn(BaseModel):
    price_cents: int


class D2dPartnerIn(BaseModel):
    partner: bool


class SpaceActionOut(BaseModel):
    space: SpaceScreenOut
    energy: EnergyOut
    unread_inbox: int
