"""Schemas for M39's data and tunables (ADR-0008, docs/formulas.md 53): `robotics.yaml` (history
to 2025, every value tagged and sourced) and the `robotics.*` keys of balance.yaml.

robotics.yaml writes values as `[value, tag]` pairs, and money as `[value, dollar year, tag]`
under keys ending `_usd` (tags as vehicles.yaml's: S sourced, D derived, R recalled from a named
source, A an assumption). These models keep the numbers and drop the tags; money becomes the
game's 2010 cents with the file's `cpi` once, at load. Model definitions only (no file reads).
"""

from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import Range, month_to_turn
from tst.sim.vehicles.config import interp

BASE_YEAR: Final = 2010  # tunable-exempt: the game's money is in 2010 dollars
CENTS: Final = 100  # tunable-exempt: unit conversion
USD_SUFFIX: Final = "_usd"  # tunable-exempt: a money key's suffix in robotics.yaml
PAIR: Final = 2  # tunable-exempt: a [value, tag] pair
TRIPLE: Final = 3  # tunable-exempt: a [value, dollar year, tag] triple
INDUSTRIAL_SEGMENTS: Final = ("automotive", "electronics", "general_industry")
HUMANOID_SEGMENTS: Final = ("logistics", "retail", "manufacturing", "consumer")
ZONE_SIZES: Final = ("small", "medium", "large")
type ZoneSize = Literal["small", "medium", "large"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _is_tagged(raw: Any) -> bool:
    return (
        isinstance(raw, list)
        and len(raw) in (PAIR, TRIPLE)
        and isinstance(raw[0], int | float)
        and isinstance(raw[-1], str)
        and all(isinstance(x, int | float) for x in raw[:-1])
    )


def _convert(raw: Any, cpi: dict[int, float], key: str = "") -> Any:
    """Drop tags and sources; `*_usd` money `[value, dollar year, tag]` -> 2010 cents under the
    key without the suffix plus `_cents` (a series of them too)."""
    if isinstance(raw, dict):
        out: dict[Any, Any] = {}
        for k, v in raw.items():
            if k == "source":
                continue
            name = str(k)
            if name.endswith(USD_SUFFIX):
                out[name[: -len(USD_SUFFIX)] + "_cents"] = _money(v, cpi)
            else:
                out[k] = _convert(v, cpi, name)
        return out
    if _is_tagged(raw):
        return raw[0]
    if isinstance(raw, list):
        return [_convert(x, cpi, key) for x in raw]
    return raw


def _money(raw: Any, cpi: dict[int, float]) -> Any:
    """`[value, dollar year, tag]` (or a `{year: ...}` series of them) -> 2010 cents."""
    if isinstance(raw, dict):
        return {k: _money(v, cpi) for k, v in raw.items()}
    if not (isinstance(raw, list) and len(raw) == TRIPLE):
        raise ValueError(f"money is [value, dollar year, tag], got {raw!r}")
    value, year = float(raw[0]), int(raw[1])
    # money-exact: rate (data's dollars into 2010 dollars at load, cents a unit)
    return value * CENTS * cpi[BASE_YEAR] / interp(cpi, year)


# --- robotics.yaml: industrial robots (53.1) -------------------------------------------------


class RegionRobotsDef(_Frozen):
    """A game region's industrial robot installations to 2025 (IFR, thousands a year, real
    world), their split by buyer industry, and its manufacturing labour cost an hour (2010
    cents) by year."""

    key: str
    installations: dict[int, float]  # thousands of robots installed a year
    segments: dict[str, float]  # buyer industry -> share of installations (sum 1)
    labour_cents: dict[int, float]  # manufacturing labour cost an hour, 2010 cents
    density: dict[int, float] = Field(default_factory=dict)  # robots per 10,000 workers (shown)

    def installed_at(self, year: float) -> float:
        return interp(self.installations, year)

    def labour_at(self, year: float) -> float:
        return interp(self.labour_cents, year)


class RobotMakerDef(_Frozen):
    """An industrial robot maker's history (53.1): an incumbents.yaml company's industrial_robots
    product, its share of each region's installations by year to 2025."""

    company: str  # incumbents.yaml name
    origin: str  # countries.yaml key
    owner: str = ""  # parent (shown): Midea from 2017, Teradyne from 2015
    share_points: dict[str, dict[int, float]] = Field(alias="shares")  # region -> year -> share

    def share_at(self, region: str, year: float) -> float:
        points = self.share_points.get(region)
        if not points:
            return 0.0
        return interp(points, year)


class PricesDef(_Frozen):
    """Industrial robot prices (2010 cents): a six-axis robot (arm and controller) and a cobot by
    year; a system's integration over the robot; a year's service as a share of the price."""

    robot_cents: dict[int, float]
    cobot_cents: dict[int, float]
    system_mult: float = Field(ge=1)
    service_share: float = Field(ge=0, le=1)  # a year's maintenance over the robot's price

    def robot_at(self, year: float) -> float:
        return interp(self.robot_cents, year)


# --- humanoids (53.2) ------------------------------------------------------------------------


class AnnouncementDef(_Frozen):
    """A humanoid announcement, pilot or launch to 2025 (shown as history; no market before the
    era)."""

    company: str  # incumbents.yaml name (a humanoid maker)
    month: str  # "YYYY-MM"
    label: str
    price_cents: float | None = None

    @property
    def turn(self) -> int:
        return month_to_turn(self.month)


class HumanoidMakerDef(_Frozen):
    company: str  # incumbents.yaml name
    origin: str
    owner: str = ""


class HumanoidsDef(_Frozen):
    era: str  # eras.yaml key that opens the market
    makers: tuple[HumanoidMakerDef, ...]
    announcements: tuple[AnnouncementDef, ...]
    price_cents: float = Field(gt=0)  # a business humanoid's price at the era's arrival
    actuator_cents: float = Field(gt=0)  # a humanoid's actuators in the first year (unit cost)
    other_cents: float = Field(gt=0)  # the rest of a humanoid's bill of materials
    workers: dict[str, dict[str, float]]  # region -> segment -> millions of workers (real)


# --- robotaxis (53.3) ------------------------------------------------------------------------


class CityDef(_Frozen):
    """A robotaxi city: its region and country, its ride-hailing market (real trips a week,
    millions, by year) and the human fare a trip (2010 cents)."""

    key: str
    label: str
    region: str
    country: str
    trips: float = Field(gt=0)  # millions of ride-hailing trips a week in 2025, real world
    fare_cents: float = Field(gt=0)  # a human ride-hail trip's average fare in 2025, 2010 cents
    km_per_trip: float = Field(gt=0)


class CityServiceDef(_Frozen):
    """A rival operator's service in a city: its driverless launch, its end (None: running), its
    fleet and its paid rides a week (real world) by year."""

    city: str
    driverless: str  # "YYYY-MM": the first public driverless rides
    end: str | None = None  # "YYYY-MM": the service stops (Cruise's suspension)
    fleet: dict[int, float]
    rides: dict[int, float]  # paid rides a week (thousands), real world

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.driverless)

    @property
    def end_turn(self) -> int | None:
        return None if self.end is None else month_to_turn(self.end)

    def running(self, turn: int) -> bool:
        end = self.end_turn
        return self.start_turn <= turn and (end is None or turn < end)


class OperatorDef(_Frozen):
    key: str
    label: str
    company: str | None = None  # incumbents.yaml name of its parent, if it is in the game
    origin: str
    ended: str | None = None  # "YYYY-MM": the programme ends (GM's Cruise, December 2024)
    services: tuple[CityServiceDef, ...]


class HistoryIncidentDef(_Frozen):
    operator: str
    city: str
    month: str
    label: str
    suspended_months: int = Field(ge=0)


class RobotaxiDef(_Frozen):
    trips_index: dict[int, float]  # ride-hailing trips by year over 2025's (1.0), world
    vehicle_cents: dict[int, float]  # a robotaxi vehicle with its sensors, 2010 cents
    sensor_cents: dict[int, float]  # the sensor and compute kit fitted to an own L4 car
    cities: tuple[CityDef, ...]
    operators: tuple[OperatorDef, ...]
    incidents: tuple[HistoryIncidentDef, ...]

    def trips_at(self, city: CityDef, year: float) -> float:
        """A city's ride-hailing trips a week (millions, real) in a year."""
        return city.trips * interp(self.trips_index, year)

    def city(self, key: str) -> CityDef | None:
        return next((c for c in self.cities if c.key == key), None)

    def city_index(self, key: str) -> int:
        return [c.key for c in self.cities].index(key)


class RoboticsFile(_Frozen):
    regions: tuple[RegionRobotsDef, ...]
    prices: PricesDef
    makers: tuple[RobotMakerDef, ...]
    humanoids: HumanoidsDef
    robotaxi: RobotaxiDef

    @model_validator(mode="before")
    @classmethod
    def _parse(cls, raw: Any) -> Any:
        if not isinstance(raw, dict) or "cpi" not in raw:
            return raw
        cpi = {int(y): float(v[0] if isinstance(v, list) else v) for y, v in raw["cpi"].items()}
        body = _convert({k: v for k, v in raw.items() if k != "cpi"}, cpi)
        body["regions"] = [{"key": k, **v} for k, v in body["regions"].items()]
        return body

    def region(self, key: str) -> RegionRobotsDef:
        return next(r for r in self.regions if r.key == key)

    def maker(self, company: str) -> RobotMakerDef | None:
        return next((m for m in self.makers if m.company == company), None)

    def humanoid_maker(self, company: str) -> HumanoidMakerDef | None:
        return next((m for m in self.humanoids.makers if m.company == company), None)


# --- balance.yaml robotics.* -------------------------------------------------------------------


class AutomationBalance(_Frozen):
    """Robots in the player's plants (53.1)."""

    plant_kinds: tuple[str, ...]  # facility kinds robots install in
    workers_per_unit: dict[str, float]  # line workers a unit a month at full capacity, by kind
    labour_share: dict[str, float]  # share of the kind's variable_cents that is line labour
    labour_per_robot: float = Field(gt=0)  # workers' worth of labour a robot replaces
    hours_per_month: float = Field(gt=0)  # a line worker's paid hours a month
    max_share: float = Field(gt=0, le=1)  # of a plant's line labour robots can replace
    life_months: int = Field(ge=1)  # a robot's straight-line depreciation
    target_level: float = Field(gt=0, le=1)  # the automation level 53.4 target 2 measures
    defect_cut: float = Field(ge=0, le=1)  # yield gain at full automation (output consistency)
    max_robots: int = Field(ge=1)  # most robots one install order may add


class HumanoidBalance(_Frozen):
    weights: dict[str, float]  # capability = hardware, ai, chips weights (sum 1)
    licensed_ai_quality: float = Field(ge=0, le=100)  # a licensed model's quality
    bought_chip_quality: float = Field(ge=0, le=100)  # a bought edge accelerator's quality
    chip_cents: float = Field(ge=0)  # a bought edge accelerator a humanoid (2010 cents)
    licence_cents: float = Field(ge=0)  # a licensed AI model's fee a humanoid sold
    learning_rate: float = Field(gt=0, lt=1)  # actuator price falls this with each doubling
    base_units: float = Field(gt=0)  # cumulative humanoids at the era's arrival (learning base)
    adoption_seed: float = Field(gt=0, lt=1)  # share of the worker pool's demand at arrival
    adoption_cap: float = Field(gt=0, lt=1)
    adoption_k: float = Field(ge=0)  # logit a year per unit of value over cost above 1
    adoption_floor_k: float = Field(ge=0)  # logit a year at least, once the era has arrived
    life_months: int = Field(ge=1)  # a humanoid's working life (its replacement cycle)
    service_share: float = Field(ge=0)  # a year's service over its price
    capability_points: float = Field(ge=0)  # feature points a capability point above 50
    home_window: Range  # years after arrival the home segment opens (seeded, hidden)
    home_share: float = Field(ge=0, le=1)  # home buyers per business worker's demand


class ZoneSizeDef(_Frozen):
    share: float = Field(gt=0, le=1)  # of the city's ride-hailing trips the zone covers
    review_months: int = Field(ge=0)  # the permit review's least length


class RobotaxiBalance(_Frozen):
    zone_sizes: dict[str, ZoneSizeDef]
    acceptance: Range  # riders' robotaxi acceptance: start and cap (share of covered trips)
    acceptance_years: float = Field(gt=0)  # years from a city's first service to half the cap
    price_elasticity: float = Field(ge=0)  # demand x (fare / price) ** this
    wait_cars: float = Field(gt=0)  # cars per 1,000 covered trips a day for half the wait share
    max_rides_per_day: float = Field(gt=0)  # a car's most rides a day (charging, cleaning)
    days_per_month: float = Field(gt=0)
    deadhead: float = Field(ge=0)  # empty km per paid km
    kwh_per_km: float = Field(gt=0)
    power_cents: float = Field(gt=0)  # a kWh of depot charging at index 1.0 (2010 cents)
    cleaning_cents: int = Field(ge=0)  # a ride
    insurance_cents: int = Field(ge=0)  # a car a month
    cars_per_operator: float = Field(gt=0)  # remote assistance: cars an operator watches
    operator_cents: int = Field(ge=0)  # a remote assistance operator a month (loaded)
    depreciation_months: int = Field(ge=1)  # a robotaxi's life
    depot_cars: int = Field(ge=1)  # cars one depot unit of capacity serves
    incident_rate: float = Field(ge=0)  # incidents per million km at maturity zero
    maturity_km: float = Field(gt=0)  # million km of a company's driverless driving to halve it
    ai_cut: float = Field(ge=0, le=1)  # rate cut at AI quality 100 (over the L4 threshold)
    serious_share: float = Field(ge=0, le=1)  # incidents that are serious (a critical event)
    minor_cents: int = Field(ge=0)  # a minor incident's cost
    serious_cents: int = Field(ge=0)  # a serious incident's cost (claims, recall of the zone)
    brand_points: dict[str, float]  # minor, serious -> brand points lost
    suspend_months: int = Field(ge=1)  # a serious incident suspends the zone's permit
    approval_chance: float = Field(ge=0, le=1)  # a month's chance of a decision, once reviewed
    refusal_share: float = Field(ge=0, le=1)  # of decisions that refuse (more with incidents)
    incident_refusal: float = Field(ge=0)  # refusal share added per serious incident (24 months)
    breakeven_rides: float = Field(gt=0)  # rides a car a day above which a fleet earns (53.4)
    rival_entry: float = Field(ge=0, le=1)  # an operator's chance a year of a new city (2026+)
    rival_fleet: float = Field(gt=0)  # a new rival city's fleet (real cars)
    rival_growth: float = Field(ge=0)  # a rival fleet's growth a year after 2025
    rides_per_car_week: float = Field(gt=0)  # a rival car's paid rides a week after 2025
    max_cars: int = Field(ge=1)  # most cars one order adds


class IncidentEventBalance(_Frozen):
    """The answers to a serious robotaxi incident (53.3, data/events/robotics.yaml)."""

    cooperate_share: float = Field(ge=0, le=1)  # of the suspension's months left kept
    cooperate_cents: int = Field(ge=0)
    compensate_cents: int = Field(ge=0)
    recover_points: float = Field(ge=0)
    contest_chance: float = Field(ge=0, le=1)  # the regulator extends the suspension
    contest_months: int = Field(ge=0)


class RoboticsBalance(_Frozen):
    start: str  # "YYYY-MM": history holds before this month
    industrial: str  # categories.yaml keys
    humanoid: str
    mobility: str
    scale: float = Field(gt=0)  # game robots = real x this (the game's economy scale)
    scale_basis: str
    growth_after: Range  # installations' annual growth after 2025, drawn by region and year
    replacement_months: dict[str, int]  # industrial segment -> (also categories.yaml)
    units_per_customer: dict[str, float]  # industrial segment -> robots a customer buys
    cobot_share: float = Field(ge=0, le=1)  # of general industry's installations (context)
    automation: AutomationBalance
    humanoids: HumanoidBalance
    robotaxi: RobotaxiBalance
    depot_kind: str  # facility.kinds key of a robotaxi depot
    rival_cash_cents: int = Field(ge=0)  # a robot maker's opening capital for its robot business
    history_months: int = Field(ge=1)
    energy: dict[str, int]  # action -> founder energy
    unlock_year: int  # the Robotics screen opens (M29)
    incident_event: IncidentEventBalance

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.start)
