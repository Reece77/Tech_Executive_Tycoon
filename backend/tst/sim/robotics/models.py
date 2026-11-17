"""Frozen robotics records (docs/formulas.md 53). GameState holds the player's plant automation
(robots installed by facility), humanoid designs (their AI model and chips), robotaxi zones and
depots, the month's zone rows and incidents, and the game-wide `RoboticsWorld` (installations'
seeded growth after 2025, humanoid adoption by region, actuator learning, rival operators' new
cities). Persisted in `robotics_record` (migration 0061_m39), one row a record.

Hidden values (53.5): `RoboticsWorld.growth` (each region's drawn path after 2025), `home_turn`
(the seeded home window) and a zone's `decision_turn` before it comes are engine-only: the API
never returns them, and incident and approval draws are never stored."""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.robotics.config import ZoneSize


@dataclass(frozen=True, slots=True)
class AutomationMonth:
    """A plant's automation in a month (53.1): what its robots saved and cost."""

    turn: int
    units: float  # units the plant ran
    saved_cents: int  # line labour the robots replaced this month
    service_cents: int
    depreciation_cents: int
    level: float  # automation level (share of line labour replaced)


@dataclass(frozen=True, slots=True)
class PlantAutomation:
    """Robots in one of the player's plants (53.1). `capex_cents` is what they cost installed (own
    robots at the group's unit cost, bought ones at the market's system price); they depreciate
    over `automation.life_months`."""

    facility_id: int
    company_id: int
    robots: int
    capex_cents: int
    depreciated_cents: int = 0
    own_robots: int = 0  # of `robots`, made by the group's own industrial robot lines
    unit_saving_cents: float = 0.0  # line labour saved a unit run this month (the plant hook)
    month: AutomationMonth | None = None
    history: tuple[AutomationMonth, ...] = ()


@dataclass(frozen=True, slots=True)
class HumanoidSpec:
    """A humanoid product's design (53.2): the AI model it runs (an own `ai_models` product, or
    licensed when None) and its chips (an own `chips_ai_accelerator` product, or bought)."""

    product_id: int
    ai_product_id: int | None = None
    chip_product_id: int | None = None


@dataclass(frozen=True, slots=True)
class ZoneMonth:
    """A zone's month (53.3): rides, utilisation and its economics."""

    turn: int
    zone_id: int
    cars: int
    rides: float
    utilisation: float  # rides over the fleet's most rides
    revenue_cents: int
    energy_cents: int
    cleaning_cents: int
    insurance_cents: int
    remote_cents: int
    depreciation_cents: int
    km: float

    @property
    def contribution_cents(self) -> int:
        return self.revenue_cents - (
            self.energy_cents
            + self.cleaning_cents
            + self.insurance_cents
            + self.remote_cents
            + self.depreciation_cents
        )


@dataclass(frozen=True, slots=True)
class Zone:
    """A robotaxi zone (53.3): a mobility product's driverless service area in a city, its permit
    and its fleet. Status: `applied` (under review), `active`, `suspended` (a serious incident:
    until `suspended_until`), `refused`, or `closed`. `decision_turn` is hidden until it comes."""

    id: int
    product_id: int
    company_id: int
    city: str  # robotics.yaml city key
    size: ZoneSize
    status: str
    applied_turn: int
    decision_turn: int | None = None  # the review's least end (hidden before)
    approved_turn: int | None = None
    suspended_until: int | None = None
    cars: int = 0
    car_product_id: int | None = None  # the group's L4 car line its cars come from (None: bought)
    capex_cents: int = 0
    depreciated_cents: int = 0
    price_cents: int = 0  # a ride (0: the city's human fare)
    km_driven: float = 0.0  # million km driverless, all time (maturity)
    event_turn: int | None = None  # the month a serious incident's critical event is shown
    month: ZoneMonth | None = None


@dataclass(frozen=True, slots=True)
class Depot:
    """A robotaxi depot (53.3): a facility (kind `depot`, capacity in depot units) in a city:
    chargers, cleaning and remote assistance."""

    facility_id: int
    company_id: int
    city: str


@dataclass(frozen=True, slots=True)
class RoboIncident:
    """A robotaxi incident that happened (53.3): public once it has. The draw is not stored."""

    turn: int
    zone_id: int
    company_id: int
    city: str
    serious: bool
    cost_cents: int
    suspended_until: int | None = None


@dataclass(frozen=True, slots=True)
class RivalCity:
    """A rival operator's service in a city after 2025 (53.3): seeded entries and growth."""

    operator: str
    city: str
    start_turn: int
    fleet: float  # real cars


@dataclass(frozen=True, slots=True)
class RoboticsWorld:
    """Game-wide robotics state. `growth`: (region, year, rate) installations' drawn growth after
    2025 (hidden); `adoption`: (region, logit) humanoid adoption once the era has arrived;
    `actuator_units` cumulative humanoids made (the learning curve, from its base); `home_turn`
    the seeded month the home segment opens (hidden); `rival_cities` operators' entries after
    2025."""

    growth: tuple[tuple[str, int, float], ...] = ()
    adoption: tuple[tuple[str, float], ...] = ()
    actuator_units: float = 0.0
    home_turn: int | None = None
    rival_cities: tuple[RivalCity, ...] = ()

    def growth_of(self, region: str, year: int) -> float | None:
        return next((g for r, y, g in self.growth if r == region and y == year), None)

    def adoption_of(self, region: str) -> float | None:
        return next((v for r, v in self.adoption if r == region), None)
