"""The living world's records (docs/formulas.md 41; ADR-0020's generic company and facility
models). All of them start empty and stay empty until `world.start` (January 2026), so a game
before 2026 holds exactly what it held before M28 (41.8 target 1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type FacilityStatus = Literal["building", "live", "mothballed", "closed"]
type CyclePhase = Literal["none", "recession", "boom", "global"]
type NewsKind = Literal[
    "deal",
    "review",
    "blocked",
    "capacity",
    "built",
    "mothball",
    "restart",
    "close",
    "executive",
    "cycle",
    "spinoff",
    "offtake",
    "china",
    "failure",
    "bid",
]
type DealStatus = Literal["review", "closed", "blocked"]
type DealKind = Literal["vertical", "horizontal", "other"]


@dataclass(frozen=True, slots=True)
class ChainCompany:
    """A chain company's world record (41.1); its company is a `CompanyState` with
    `rival_key = (CHAIN_KEY, index)`. `executives` are (role, name), the CEO first: named
    characters with the company's personality, not people on a payroll."""

    company_id: int
    key: str  # chain_companies.yaml / suppliers.yaml / nodes.yaml key, or other_<good>
    index: int  # stable key position (tst.sim.world.data)
    country: str
    region: str
    executives: tuple[tuple[str, str], ...] = ()
    ceo_since: int = 0
    insolvent_months: int = 0
    is_other: bool = False
    revenue_cents: int = 0  # last month's
    costs_cents: int = 0  # last month's cash costs (cost of goods, fixed costs and interest)
    ebitda: tuple[int, ...] = ()  # the last 12 months' EBITDA, oldest first


@dataclass(frozen=True, slots=True)
class WorldFacility:
    """A chain company's facility (41.1): a simplified kind of the generic facility model.
    `capacity` is units of its good a year; `cost` its position on the good's cost curve."""

    id: int
    company_id: int
    good: str
    country: str
    region: str
    capacity: float
    cost: float
    status: FacilityStatus
    ordered_turn: int
    ready_turn: int
    capex_cents: int = 0  # what it cost to build (opening plant: its book at the start)
    depreciated_cents: int = 0
    below_months: int = 0  # months in a row spot was under its cash cost
    above_months: int = 0  # mothballed: months in a row spot topped cost x (1 + hurdle)
    mothballed_turn: int | None = None
    closed_turn: int | None = None
    output: float = 0.0  # last month's output, units a month

    def live(self, turn: int) -> bool:
        return self.status == "live" or (self.status == "building" and self.ready_turn <= turn)


@dataclass(frozen=True, slots=True)
class WorldGood:
    """A good's last world month (41.2): capacities and flows a year, and the balance factor
    the next month's price takes. `prices` are the last 12 months' prices in the good's unit
    (dollars a wafer for foundry wafers), oldest first, for the 3-year outlook."""

    good: str
    turn: int
    capacity: float
    supply: float
    demand: float
    player_supply: float
    player_demand: float
    factor: float
    prices: tuple[float, ...] = ()
    contracted: float = 0.0  # rivals' offtakes running, a year (41.3)
    output: float = 0.0  # what producers actually made, the player's included, a year
    short_months: int = 0  # months in a row supply was under 70% of demand (41.8 target 3)


@dataclass(frozen=True, slots=True)
class RegionCycle:
    """A region's demand cycle after 2025 (41.6). `level` is the AR(1) around 1; a phase
    (recession, boom or a global shock) adds its depth, easing in and out over its months."""

    region: str
    turn: int
    level: float = 1.0
    phase: CyclePhase = "none"
    phase_start: int = 0
    phase_months: int = 0
    depth: float = 0.0  # signed: negative in a recession or shock
    multiplier: float = 1.0
    previous: float = 1.0  # last month's multiplier (demand grows by the ratio)


@dataclass(frozen=True, slots=True)
class WorldNews:
    """One World news item (41.7), with what it links to."""

    id: int
    turn: int
    kind: NewsKind
    message: str
    company_id: int | None = None
    other_id: int | None = None
    region: str | None = None
    good: str | None = None


@dataclass(frozen=True, slots=True)
class RivalDeal:
    """A rival buying another company (41.3): agreed, reviewed, closed or blocked."""

    id: int
    agreed_turn: int
    buyer_id: int
    target_id: int
    price_cents: int
    kind: DealKind
    status: DealStatus
    close_turn: int  # the month it closes or is refused
    share: float = 0.0  # the highest combined share the antitrust test found


@dataclass(frozen=True, slots=True)
class RivalMandate:
    """What a rival owner runs a subsidiary for (41.3, 31.4's kinds)."""

    company_id: int
    owner_id: int
    kind: Literal["grow", "margin", "cash"]
    set_turn: int


@dataclass(frozen=True, slots=True)
class WorldOfftake:
    """A device or chip rival's offtake with a chain company (41.3), units a year."""

    id: int
    buyer_id: int
    seller_id: int
    good: str
    volume: float
    start_turn: int
    end_turn: int


@dataclass(frozen=True, slots=True)
class WorldBid:
    """A rival's bid for the player's listed group (41.4): at most one a year per rival. The
    rival's valuation behind it is never stored or shown (41.9)."""

    id: int
    rival_id: int
    turn: int
    price_cents: int  # a share
    status: Literal["open", "accepted", "rejected", "lapsed"] = "open"


@dataclass(frozen=True, slots=True)
class ChinaLag:
    """A Chinese foundry's research lag after 2025 (41.5), in generations behind the leading
    node, and the nodes it reached after 2025 with their months."""

    foundry: str
    turn: int
    behind: float
    reached: tuple[tuple[str, int], ...] = ()
    binding: bool = False
