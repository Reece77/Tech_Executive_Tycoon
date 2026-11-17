"""Frozen vehicle records (docs/formulas.md 49). GameState holds every car's design (its spec),
the player's cell plants and charging networks, the month's own-cell lots, incidents and recalls,
each product's software month, and the game-wide `VehicleWorld` (the EV-share paths and the
learning rate after 2025, approvals and suspensions). Persisted in `vehicle_record` (migration
0058_m38), one row a record.

Hidden values: `VehicleWorld.k` (each region's drawn S-curve speed), `learning_rate` and a cell
plant's `overrun` are engine-only; the API never returns them (formulas.md 49.7)."""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.vehicles.config import Chemistry, Level, PlatformChoice


@dataclass(frozen=True, slots=True)
class VehicleSpec:
    """A vehicle product's design (49.1): pack, chemistry, charging, autonomy, platform and cell
    source. `cells` is a cell maker key, or "own" for the group's cells (bought where short)."""

    product_id: int
    pack_kwh: float
    chemistry: Chemistry
    charge_kw: float
    autonomy: Level  # the level the design aims for; what it reaches is `level_reached`
    platform: PlatformChoice
    cells: str
    origin: str = ""  # countries.yaml key where its cars are made (rivals: the data's)
    os_product_id: int | None = None  # an own OS product (platform "own")


@dataclass(frozen=True, slots=True)
class CellPlantMonth:
    """A cell plant's month (49.2): kWh made, where they went and what they cost."""

    turn: int
    capacity_kwh: float
    made_kwh: float
    to_group: float = 0.0
    to_spot: float = 0.0
    inputs: tuple[tuple[str, float], ...] = ()  # (commodity, volume) bought or taken
    input_cents: int = 0
    power_cents: int = 0
    other_cents: int = 0
    fixed_cents: int = 0
    revenue_cents: int = 0  # spot sales
    unit_cents: float = 0.0  # cost a kWh made (inputs, power, other, fixed; depreciation too)
    yield_rate: float = 0.0


@dataclass(frozen=True, slots=True)
class CellPlant:
    """An own cell plant (49.2): a facility (kind `cell_plant`) and its chemistry and learning.
    `overrun` is hidden (the capex already reflects it)."""

    facility_id: int
    company_id: int
    chemistry: Chemistry
    estimate_cents: int = 0  # the quote at the order (shown; the true capex is revealed as paid)
    months_run: int = 0
    yield_rate: float = 0.0
    overrun: float = 0.0
    month: CellPlantMonth | None = None
    history: tuple[CellPlantMonth, ...] = ()


@dataclass(frozen=True, slots=True)
class CellLot:
    """Own cells handed to the group's cars this month (49.2, as M20's OwnSupply)."""

    turn: int
    facility_id: int
    seller_id: int
    buyer_id: int
    product_id: int
    kwh: float
    unit_cents: float  # transfer price a kWh
    market_cents: float  # the market's price a kWh this month
    taken: float = 0.0


@dataclass(frozen=True, slots=True)
class ChargingMonth:
    turn: int
    kwh_sold: float
    revenue_cents: int
    energy_cents: int
    use: float


@dataclass(frozen=True, slots=True)
class ChargingNetwork:
    """A charging network (49.5): one region's sites (a facility, kind `charging_network`, its
    capacity in chargers), open to every EV or exclusive to the owner's cars."""

    facility_id: int
    company_id: int
    region: str
    exclusive: bool = False
    month: ChargingMonth | None = None
    history: tuple[ChargingMonth, ...] = ()


@dataclass(frozen=True, slots=True)
class VehicleMonth:
    """A vehicle product's month (49.1, 49.3): cars sold, its unit cost by line and its
    software revenue, for the product pages."""

    turn: int
    product_id: int
    units: float
    battery_cents: float  # a car's pack at this month's cell price (own cells at cost)
    drive_cents: float
    chips_cents: float
    body_cents: float
    assembly_cents: float
    own_kwh: float  # kWh of the month's packs from own cells
    software_cents: int  # subscriptions this month
    licence_cents: int  # the platform's licence on the month's cars
    level: str  # the autonomy level its cars run (where approved: the best region's)
    range_km: float
    subsidy_regions: tuple[tuple[str, bool], ...] = ()  # (region, eligible) where one runs


@dataclass(frozen=True, slots=True)
class Incident:
    """An autonomy incident that happened (49.4): public once it has. The draw is not stored."""

    turn: int
    product_id: int
    company_id: int
    region: str
    level: str
    cars_recalled: float
    cost_cents: int


@dataclass(frozen=True, slots=True)
class Suspension:
    """A regulator's suspension of a level's approval for one company's cars in a region."""

    company_id: int
    region: str
    level: str
    until_turn: int


@dataclass(frozen=True, slots=True)
class VehicleWorld:
    """Game-wide vehicle state. Before `vehicles.start` everything is the data's; from it the
    EV share's logit per region (`logit`), each region's drawn speed (`k`, hidden), the learning
    rate (hidden, drawn once), cumulative cell production (GWh) and the approvals made after the
    history (`approved`: (region, level, turn))."""

    logit: tuple[tuple[str, float], ...] = ()
    k: tuple[tuple[str, float], ...] = ()
    learning_rate: float | None = None
    cumulative_gwh: float = 0.0
    base_cumulative_gwh: float = 0.0
    approved: tuple[tuple[str, str, int], ...] = ()
    suspensions: tuple[Suspension, ...] = ()

    def logit_of(self, region: str) -> float | None:
        return next((v for r, v in self.logit if r == region), None)

    def k_of(self, region: str) -> float | None:
        return next((v for r, v in self.k if r == region), None)
