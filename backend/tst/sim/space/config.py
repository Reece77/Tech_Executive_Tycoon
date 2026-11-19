"""Schemas for M40's data and tunables (ADR-0008, docs/formulas.md 56): `space.yaml` (history to
2025, every value tagged and sourced) and the `space.*` keys of balance.yaml.

space.yaml writes values as `[value, tag]` pairs and money as `[value, dollar year, tag]` under keys
ending `_usd` (tags as robotics.yaml's: S sourced, D derived, R recalled from a named source, A an
assumption). These models keep the numbers and drop the tags; money becomes the game's 2010 cents
with the file's `cpi` once, at load (robotics.yaml's conversion). Model definitions only.
"""

from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import Range, month_to_turn
from tst.sim.robotics.config import _convert
from tst.sim.vehicles.config import interp

type ReuseLevel = Literal["expendable", "recovery", "full"]
YEAR_CHARS: Final = 4  # tunable-exempt: "YYYY-MM"'s year
REUSE_LEVELS: Final[tuple[ReuseLevel, ...]] = ("expendable", "recovery", "full")
CONSTELLATION_KINDS: Final = ("broadband", "eo")
type ConstellationKind = Literal["broadband", "eo"]
LAUNCH_SEGMENTS: Final = ("satellite_operators", "government")
BROADBAND_SEGMENTS: Final = (
    "consumer",
    "enterprise",
    "aviation_maritime",
    "government",
    "direct_to_device",
)
EO_SEGMENTS: Final = ("enterprise", "government")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --- space.yaml: launch (56.1) -----------------------------------------------------------------


class ProviderDef(_Frozen):
    """A launch provider's orbital launches a year to 2025 (real world): an incumbents.yaml
    company's `launch` line, whose share of the launch market is its share of the year's launches
    (pinned to December 2025, 56.4 target 1)."""

    company: str  # incumbents.yaml name
    origin: str  # countries.yaml key
    launches: dict[int, float]  # orbital launch attempts a year
    failures: dict[int, float] = Field(default_factory=dict)  # of them, failed (shown)
    first: str = ""  # "YYYY-MM": its first orbital launch in the game's years (none before)

    def launches_at(self, year: float) -> float:
        if self.first and year < int(self.first[:YEAR_CHARS]):
            return 0.0
        return interp(self.launches, year)

    @property
    def first_turn(self) -> int | None:
        return month_to_turn(self.first) if self.first else None


class VehicleDef(_Frozen):
    """A historical launch vehicle (shown, and the price a bought launch pays): its maker, first
    flight, payload to low Earth orbit and price a launch (2010 cents) by year."""

    key: str
    label: str
    company: str  # incumbents.yaml name, or a maker outside the game (NASA's Shuttle)
    first_flight: str  # "YYYY-MM"
    retired: str = ""  # "YYYY-MM": its last flight
    payload_kg: float = Field(gt=0)  # to low Earth orbit (its reusable configuration when reused)
    price_cents: dict[int, float]  # a launch's list price by year, 2010 cents
    reusable_from: str = ""  # "YYYY-MM": the first reflight of a booster (a reused configuration)
    target: bool = False  # a stated target, not a flown price (Starship)

    @property
    def first_turn(self) -> int:
        return month_to_turn(self.first_flight)

    @property
    def retired_turn(self) -> int | None:
        return month_to_turn(self.retired) if self.retired else None

    def flying(self, turn: int) -> bool:
        end = self.retired_turn
        return not self.target and self.first_turn <= turn and (end is None or turn <= end)

    def price_at(self, year: float) -> float:
        return interp(self.price_cents, year)

    def cost_per_kg_at(self, year: float) -> float:
        return self.price_at(year) / self.payload_kg


class MilestoneDef(_Frozen):
    """A reuse or programme milestone (shown as history)."""

    month: str
    label: str

    @property
    def turn(self) -> int:
        return month_to_turn(self.month)


class EarlyFailuresDef(_Frozen):
    """A new vehicle's early record (the failure model's calibration, 56.4 target 4)."""

    vehicle: str
    flights: int = Field(ge=1)
    failures: int = Field(ge=0)


class LaunchFile(_Frozen):
    world: dict[int, float]  # orbital launch attempts a year, world
    providers: tuple[ProviderDef, ...]
    vehicles: tuple[VehicleDef, ...]
    milestones: tuple[MilestoneDef, ...]
    early_failures: tuple[EarlyFailuresDef, ...]
    bought_vehicle: str  # VehicleDef key whose price a bought launch pays before 2026

    def world_at(self, year: float) -> float:
        return interp(self.world, year)

    def vehicle(self, key: str) -> VehicleDef | None:
        return next((v for v in self.vehicles if v.key == key), None)

    def provider(self, company: str) -> ProviderDef | None:
        return next((p for p in self.providers if p.company == company), None)


# --- space.yaml: constellations and services (56.2-56.3) ----------------------------------------


class ConstellationDef(_Frozen):
    """A rival constellation's history (shown; its operator's broadband or EO line is pinned to
    its subscribers to 2025)."""

    key: str
    label: str
    company: str  # incumbents.yaml name
    kind: ConstellationKind
    first_launch: str  # "YYYY-MM"
    service: str  # "YYYY-MM": its service opened (no price before)
    d2d: bool = False  # it serves phones directly (from d2d.open)
    satellites: dict[int, float]  # in orbit at year end, real world
    subscribers: dict[int, float] = Field(default_factory=dict)  # thousands at year end, real
    licensed: dict[str, str] = Field(default_factory=dict)  # region -> "YYYY-MM" service opened

    @property
    def first_turn(self) -> int:
        return month_to_turn(self.first_launch)

    @property
    def service_turn(self) -> int:
        return month_to_turn(self.service)

    def satellites_at(self, year: float) -> float:
        if year < int(self.first_launch[:YEAR_CHARS]):
            return 0.0
        return interp(self.satellites, year)

    def subscribers_at(self, year: float) -> float:
        if not self.subscribers:
            return 0.0
        return interp(self.subscribers, year)


class D2dDef(_Frozen):
    """Direct-to-device's history: the month a commercial service opened (the segment's sellers
    have no price before it) and its milestones."""

    open: str  # "YYYY-MM"
    milestones: tuple[MilestoneDef, ...]

    @property
    def open_turn(self) -> int:
        return month_to_turn(self.open)


class MarketSizeDef(_Frozen):
    """A published market size (context for 56's calibration; the game's markets are sized by
    categories.yaml and M43a's ceilings)."""

    key: str
    label: str
    year: int
    size_cents: float = Field(gt=0)  # 2010 cents a year


class SpaceFile(_Frozen):
    launch: LaunchFile
    constellations: tuple[ConstellationDef, ...]
    d2d: D2dDef
    terminal_cost_cents: dict[int, float]  # a broadband user terminal's cost to make, 2010 cents
    satellite_cost_cents: dict[int, float]  # a LEO broadband satellite's cost a kg, 2010 cents
    markets: tuple[MarketSizeDef, ...]

    @model_validator(mode="before")
    @classmethod
    def _parse(cls, raw: Any) -> Any:
        if not isinstance(raw, dict) or "cpi" not in raw:
            return raw
        cpi = {int(y): float(v[0] if isinstance(v, list) else v) for y, v in raw["cpi"].items()}
        return _convert({k: v for k, v in raw.items() if k != "cpi"}, cpi)

    def constellation(self, key: str) -> ConstellationDef | None:
        return next((c for c in self.constellations if c.key == key), None)

    def constellation_of(self, company: str, kind: str) -> ConstellationDef | None:
        return next(
            (c for c in self.constellations if c.company == company and c.kind == kind), None
        )


# --- balance.yaml space.* ------------------------------------------------------------------------


class ReuseLevelBalance(_Frozen):
    """What a reuse level needs (lead points in the `reusability` domain over its baseline) and
    gives (56.1): the share of the vehicle's build cost that flies again, how many flights it
    lasts, its refurbishment a flight (share of that part's cost), the payload given up to recover
    it, and a pad's launches a month (turnaround)."""

    label: str
    lead: float = Field(ge=0)
    min_months: int = Field(ge=0)  # months since the company's reusability programme began
    reused_share: float = Field(ge=0, le=1)
    flights: int = Field(ge=1)
    refurb_share: float = Field(ge=0, le=1)
    payload_cut: float = Field(ge=0, lt=1)
    pad_rate: float = Field(gt=0)  # launches a month one launch-site unit supports


class VehicleBalance(_Frozen):
    payload_kg: Range  # a design's payload to LEO (expendable)
    build_cents_per_kg: float = Field(gt=0)  # an expendable vehicle's build cost a kg of payload
    size_exponent: float = Field(gt=0, le=1)  # build cost x (payload / ref) ** this
    ref_payload_kg: float = Field(gt=0)
    ops_cents_per_kg: float = Field(ge=0)  # range, propellant and launch operations a flight
    quality_cost: float = Field(ge=0)  # build cost x (1 + this x (quality - 50) / 100)
    learning_rate: float = Field(ge=0, lt=1)  # build cost falls this a doubling of flights
    max_learning_flights: int = Field(ge=1)


class FailureBalance(_Frozen):
    """A flight's failure chance (56.1): floor + (new_rate - floor) x 0.5 ** (flights flown /
    half_flights), x (1 + quality_k x (60 - quality) / 100), at most max_rate."""

    new_rate: float = Field(ge=0, le=1)
    floor: float = Field(ge=0, le=1)
    half_flights: float = Field(gt=0)
    quality_k: float = Field(ge=0)
    max_rate: float = Field(gt=0, le=1)
    ground_months: Range  # the investigation that grounds a vehicle after a failure
    brand_points: float = Field(ge=0)  # brand lost on the launch line
    insured_share: float = Field(ge=0, le=1)  # of an insured payload's value the policy pays
    premium_rate: float = Field(ge=0, le=1)  # of the insured value, a launch


class SatelliteBalance(_Frozen):
    mass_kg: Range  # a design's mass
    gbps_per_kg: float = Field(gt=0)  # broadband capacity a kg of satellite (Gbps)
    life_months: Range  # a design's life
    life_cost: float = Field(ge=0)  # cost x (1 + this x (life - lo) / (hi - lo))
    eo_cost_mult: float = Field(gt=0)  # an imaging satellite's cost a kg over a broadband one's
    chip_share: float = Field(ge=0, le=1)  # of a satellite's cost that is its processors
    own_chip_cut: float = Field(ge=0, le=1)  # of the chip share saved with the group's own chips
    bought_mult: float = Field(ge=1)  # a satellite bought from a maker x the made cost
    bought_per_month: int = Field(ge=0)  # most satellites a constellation can buy a month


class ShellBalance(_Frozen):
    label: str
    regions: tuple[str, ...]  # regions a complete shell opens (empty: capacity only)


class ConstellationBalance(_Frozen):
    shell_sats: int = Field(ge=1)  # satellites in a shell (real shell x space.scale)
    shells: tuple[ShellBalance, ...]
    complete_share: float = Field(gt=0, le=1)  # of a shell in orbit for its regions to open
    subs_per_gbps: float = Field(gt=0)  # subscribers a Gbps of capacity serves (oversubscribed)
    congestion_k: float = Field(ge=0)  # appeal x (capacity / subscribers) ** this when over
    ground_station_cents: int = Field(ge=0)  # ground stations a covered region a month
    deorbit_cents: int = Field(ge=0)  # a satellite's disposal at its end of life
    eo_min_satellites: int = Field(ge=1)  # an EO constellation sells from this many in orbit
    eo_gbps: float = Field(ge=0)  # unused by EO; kept 0
    replace_ahead_months: int = Field(ge=0)  # satellites retiring within this are replaced ahead
    history_months: int = Field(ge=1)  # constellation months kept
    max_shells: int = Field(ge=1)


class TerminalBalance(_Frozen):
    learning_rate: float = Field(ge=0, lt=1)  # terminal cost falls this a doubling of made
    base_units: float = Field(gt=0)  # the learning curve's base (game units)
    amortize_months: int = Field(ge=1)  # a terminal's price spread over this in buyers' appeal


class LicenceBalance(_Frozen):
    review_months: dict[str, int]  # region -> the review's least length
    approval: dict[str, float]  # region -> a decision's chance of approval
    decision_chance: float = Field(gt=0, le=1)  # a month's chance of a decision, once reviewed
    fee_cents: int = Field(ge=0)  # an application's fee
    relation_cut: float = Field(ge=0, le=1)  # approval x (1 - this) where relations are hostile


class DebrisBalance(_Frozen):
    window: Range  # years after space.start a tighter debris rule arrives (seeded, hidden)
    fee_cents: int = Field(ge=0)  # a satellite in orbit a month under the tighter rule
    deorbit_mult: float = Field(ge=1)  # disposal cost x this under it


class D2dBalance(_Frozen):
    partner_share: float = Field(ge=0, le=1)  # of D2D revenue a carrier partner keeps
    partner_appeal: float = Field(ge=1)  # appeal x this with a carrier partner
    gbps_share: float = Field(ge=0, le=1)  # of a D2D-capable satellite's capacity for phones
    subs_per_gbps: float = Field(gt=0)  # D2D subscribers a Gbps serves (texting and data)
    cost_mult: float = Field(ge=1)  # a D2D-capable satellite's cost x this


class EventBalance(_Frozen):
    """The answers to a launch failure with the player's satellites aboard (56.1)."""

    review_cut: float = Field(ge=0, le=1)  # an independent review shortens the grounding
    review_cents: int = Field(ge=0)
    rebuild_cents: int = Field(ge=0)  # rush replacements: each lost satellite rebuilt at once
    claim_chance: float = Field(ge=0, le=1)  # contest the insurer: the rest of the value paid
    claim_cents: int = Field(ge=0)  # legal costs of contesting


class SpaceBalance(_Frozen):
    start: str  # "YYYY-MM": history holds before this month
    launch: str  # categories.yaml keys
    broadband: str
    eo: str
    d2d_segment: str
    domain: str  # tech_frontier.yaml key of the reusability domain
    scale: float = Field(gt=0)
    scale_basis: str
    site_kind: str  # facility.kinds key of a launch site
    plant_kind: str  # facility.kinds key of a satellite plant
    site_regions: tuple[str, ...]  # regions with launch ranges (a site needs one)
    reuse: dict[str, ReuseLevelBalance]
    vehicle: VehicleBalance
    failure: FailureBalance
    satellite: SatelliteBalance
    constellation: ConstellationBalance
    terminal: TerminalBalance
    licence: LicenceBalance
    debris: DebrisBalance
    d2d: D2dBalance
    broadband_churn_mult: float = Field(gt=0, le=1)  # x a broadband line's base churn
    history_split: dict[str, float]  # broadband segment -> share of an operator's subscribers
    history_share: dict[str, float]  # EO operator (incumbents.yaml) -> its share to 2025
    rival_growth: Range  # rivals' launches and satellites a year after 2025, drawn yearly
    rival_cash_cents: int = Field(ge=0)
    max_launches_month: int = Field(ge=1)  # most launches a constellation plan asks a month
    history_months: int = Field(ge=1)  # launches kept
    energy: dict[str, int]
    unlock_year: int
    event: EventBalance

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.start)

    @model_validator(mode="after")
    def _levels(self) -> SpaceBalance:
        if set(self.reuse) != set(REUSE_LEVELS):
            raise ValueError(f"space.reuse lists {list(REUSE_LEVELS)}")
        return self
