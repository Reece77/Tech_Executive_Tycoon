"""M32 records (docs/formulas.md 46, ADR-0022): plants, power-purchase agreements, grid-queue
entries, each company's monthly power book by region, grid outages that happened, and each
region's seeded path after 2025.

A plant is a `Facility` of kind `plant` (ADR-0020's one facility model); `Plant` holds what only
plants have, keyed by the facility's id, as fabs do. Every record belongs to a `company_id`.
Hidden values: a plant's `complete_turn` (its true completion, carrying the overrun's delay) and
the facility's `capex_cents` (the overrun); neither reaches the API until it happens (46.9).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type PpaStatus = Literal["active", "ended", "terminated"]
type QueueKind = Literal["plant", "load"]


@dataclass(frozen=True, slots=True)
class PlantMonth:
    """One month of a plant (46.2), as the plant page shows it. Energy in MWh, money in cents."""

    turn: int
    output_mwh: float = 0.0  # what it generated
    used_mwh: float = 0.0  # what the company's own facilities took
    exported_mwh: float = 0.0  # surplus sold to the grid
    curtailed_mwh: float = 0.0  # surplus a behind-the-meter or unconnected plant could not sell
    fuel_cents: int = 0
    om_cents: int = 0  # fixed and variable operating cost
    carbon_cents: int = 0
    grid_charge_cents: int = 0  # network charges on energy used off-site
    export_cents: int = 0  # surplus sales
    displaced_cents: int = 0  # grid energy it replaced, at the grid price
    tonnes: float = 0.0  # scope 1 tCO2
    offline: bool = False  # in a forced outage this month


@dataclass(frozen=True, slots=True)
class Plant:
    """A plant's own state (46.2). `estimate_cents` is the quoted capex; the facility's
    `capex_cents` carries the hidden overrun, revealed as it is paid, and `complete_turn` the
    true completion (later than the quote by the overrun's delay). It generates from the later of
    completion and its grid connection (a behind-the-meter plant needs none)."""

    facility_id: int
    company_id: int
    type: str  # power.yaml plant type
    mw: float
    estimate_cents: int
    complete_turn: int
    monthly_capex_cents: int  # paid each month until the capex is paid
    site_id: int | None = None  # behind the meter at this facility (same company and city)
    queue_id: int | None = None  # its grid-queue entry (a grid-tied plant)
    connected: bool = False  # the grid connection is done (or it needs none)
    live_turn: int | None = None
    outage_until: int | None = None  # last month of a forced outage
    month: PlantMonth | None = None

    def live(self, turn: int) -> bool:
        return self.live_turn is not None and self.live_turn <= turn

    def offline(self, turn: int) -> bool:
        """In a forced outage this month (46.5)."""
        return self.outage_until is not None and turn <= self.outage_until


@dataclass(frozen=True, slots=True)
class Ppa:
    """A power-purchase agreement (46.2): `mwh_month` at `price` cents a MWh from `start_turn`
    to `end_turn` (inclusive), take-or-pay on what is not taken (33.3)."""

    id: int
    company_id: int
    region: str
    producer: str  # power.yaml producer key
    mwh_month: float
    price_cents: float  # a MWh (2010 cents)
    signed_turn: int
    start_turn: int
    end_turn: int
    status: PpaStatus = "active"
    used_mwh: float = 0.0  # last month's
    paid_cents: int = 0  # last month's

    def running(self, turn: int) -> bool:
        return self.status == "active" and self.start_turn <= turn <= self.end_turn


@dataclass(frozen=True, slots=True)
class QueueEntry:
    """A project waiting for its grid connection (46.3): a plant, or a data centre or fab (a
    load). It connects with a monthly hazard after `min_turn`; no future draw is stored."""

    id: int
    company_id: int
    region: str
    facility_id: int
    kind: QueueKind
    mw: float
    joined_turn: int
    median_months: float  # the region's median wait when it joined (the screen shows a range)
    connected_turn: int | None = None


@dataclass(frozen=True, slots=True)
class PowerMonth:
    """A company's month of power in one region (46.1-46.5): energy in MWh, money in cents."""

    company_id: int
    region: str
    turn: int
    demand_mwh: float = 0.0
    plant_mwh: float = 0.0  # own plants' energy used
    ppa_mwh: float = 0.0
    grid_mwh: float = 0.0
    exported_mwh: float = 0.0
    grid_price_cents: float = 0.0  # a MWh this month
    grid_cents: int = 0  # what the facilities paid at the grid price
    net_cents: int = 0  # the month's energy cost after settlement (plants, PPAs, exports)
    scope1_tonnes: float = 0.0
    scope2_tonnes: float = 0.0
    peak_mw: float = 0.0
    outage: bool = False
    wafers_lost: float = 0.0


@dataclass(frozen=True, slots=True)
class GridOutage:
    """A grid outage that happened (46.5): region and month."""

    turn: int
    region: str


@dataclass(frozen=True, slots=True)
class RegionPath:
    """A region's power path for a year after 2025 (46.3, 46.4): seeded each December for the
    next year; nothing beyond the current year is stored (46.9)."""

    region: str
    year: int
    carbon: float  # $/t (2010 dollars)
    intensity: float  # tCO2 a MWh of the grid
    queue_months: float  # median wait


@dataclass(frozen=True, slots=True)
class PowerWorld:
    """Game-wide draws (46.2): each plant type's yearly learning after 2025 and the SMR era's
    first year, drawn once at `power.plants.smr_start`; plants unlocked per company."""

    learning: tuple[tuple[str, float], ...] = ()
    smr_year: int | None = None
    unlocked: tuple[int, ...] = ()  # companies whose plant one-off is done (stage 4 reached)
