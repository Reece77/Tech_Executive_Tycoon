"""Schemas for M38's data and tunables (ADR-0008, docs/formulas.md 49): `vehicles.yaml` (history
to 2025, every value tagged and sourced) and the `vehicles.*` keys of balance.yaml.

vehicles.yaml writes most values as `[value, tag]` pairs (tags as power.yaml's: S sourced, D
derived, R recalled from a named source, A an assumption); these models keep the numbers and drop
the tags. Real money is converted to the game's 2010 dollars with the file's `cpi` once, at load.
Model definitions only (no file reads), so `tst.sim.data_models` can import them without a cycle.
"""

from __future__ import annotations

import itertools
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import Range, month_to_turn

BASE_YEAR: Final = 2010  # tunable-exempt: the game's money is in 2010 dollars
MONTHS: Final = 12  # tunable-exempt: calendar
CHEMISTRIES: Final = ("nmc", "lfp")
type Chemistry = Literal["nmc", "lfp"]
LEVELS: Final = ("none", "l2", "l2_plus", "l3", "l4")
type Level = Literal["none", "l2", "l2_plus", "l3", "l4"]
PLATFORM_CHOICES: Final = ("own", "licensed", "closed")
type PlatformChoice = Literal["own", "licensed", "closed"]
OWN: Final = "own"  # tunable-exempt: a product's cell source when it uses the group's cells


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def interp(points: dict[int, float], year: float) -> float:
    """Linear between year points, held at the ends."""
    pts = sorted(points.items())
    if year <= pts[0][0]:
        return pts[0][1]
    for (y0, v0), (y1, v1) in itertools.pairwise(pts):
        if year <= y1:
            return v0 + (v1 - v0) * (year - y0) / (y1 - y0)
    return pts[-1][1]


def _value(raw: Any) -> float:
    """A tagged scalar `[value, tag]` (or a bare number) -> the value."""
    if isinstance(raw, list | tuple):
        return float(raw[0])
    return float(raw)


def _series(raw: Any) -> dict[int, float]:
    """`{year: [value, tag], ...}` -> `{year: value}`."""
    if not isinstance(raw, dict):
        return {}
    return {int(y): _value(v) for y, v in raw.items()}


def _year_of(month: str) -> int:
    return int(str(month)[:4])


def _strip(raw: Any) -> Any:
    """Drop the tags of every `[number, "tag"]` pair in a nested structure."""
    if isinstance(raw, dict):
        return {k: _strip(v) for k, v in raw.items()}
    if (
        isinstance(raw, list)
        and len(raw) == 2  # tunable-exempt: a [value, tag] pair
        and isinstance(raw[0], int | float)
        and isinstance(raw[1], str)
    ):
        return raw[0]
    if isinstance(raw, list):
        return [_strip(x) for x in raw]
    return raw


# --- vehicles.yaml ------------------------------------------------------------------------------


class RegionCarsDef(_Frozen):
    """A game region's car market to 2025 (49.1, 49.5): new cars sold a year (millions, real),
    the electric share of them, public charging points (thousands) and the segment split."""

    key: str
    car_sales: dict[int, float]  # millions of new cars a year, real world
    ev_share: dict[int, float]  # electric (BEV + PHEV) share of new car sales, 0-1
    chargers: dict[int, float]  # public charging points, thousands
    segments: dict[str, float]  # segment -> share of new car buyers (sum 1)

    def sales_at(self, year: float) -> float:
        return interp(self.car_sales, year)

    def share_at(self, year: float) -> float:
        return interp(self.ev_share, year)

    def chargers_at(self, year: float) -> float:
        return interp(self.chargers, year)


class ChemistryDef(_Frozen):
    """A cell chemistry (49.2): energy density, cost and range against NMC, materials a kWh."""

    label: str
    wh_per_kg: float = Field(gt=0)  # cell-level energy density (2024)
    cost_mult: float = Field(gt=0)  # cell price x this (NMC 1.0)
    range_mult: float = Field(gt=0)  # km a kWh x this: a heavier pack goes less far
    inputs: dict[str, float]  # commodities.yaml key -> volume units (t or kg) a kWh of cells


class BatteryDef(_Frozen):
    """Battery pack prices to 2025 (BNEF, 2010 dollars at load) and the cell share of a pack."""

    pack_cents: dict[int, float]  # cents a kWh, volume-weighted pack price (2010 dollars)
    cell_share: dict[int, float]  # share of the pack price that is the cells
    chemistries: dict[str, ChemistryDef]
    lfp_share: dict[int, float]  # LFP's share of EV cells (context; rivals' and the mix's)

    def pack_at(self, year: float) -> float:
        return interp(self.pack_cents, year)

    def cell_share_at(self, year: float) -> float:
        return interp(self.cell_share, year)


class CellMakerDef(_Frozen):
    """A cell maker (49.2): a chain company of `battery_cells` (41.1) and a supplier the player's
    cars can buy from (its origin country decides subsidy rules and tariffs)."""

    key: str = Field(min_length=1)
    name: str
    country: str  # countries.yaml key where its cells are made (its main base)
    share: dict[int, float]  # share of world EV cell supply by year
    gwh: dict[int, float] = Field(default_factory=dict)  # installed GWh a year (context)
    price_mult: float = Field(gt=0)  # its cells' price x the market's
    chemistries: tuple[Chemistry, ...] = CHEMISTRIES


class RivalCarsDef(_Frozen):
    """A car maker's EV history (49.1): an incumbents.yaml company's vehicles product, its
    shares of each region's EV sales by year to 2025, where its cars are made and when it
    launched its first EV in the game's terms."""

    company: str  # incumbents.yaml name
    origin: str  # countries.yaml key of its main production (tariffs, subsidies)
    cells: str  # cell maker key its cars use (subsidy sourcing rules)
    launch: str | None = None  # "YYYY-MM" of its first sales; None: selling in January 2010
    shares: dict[str, dict[int, float]]  # region -> year -> share of the region's EV sales

    @property
    def launch_turn(self) -> int:
        return 0 if self.launch is None else month_to_turn(self.launch)

    def share_at(self, region: str, year: float, turn: int | None = None) -> float:
        """The share at a fractional year: linear between points, held after the last, and
        rising from 0 over the year before a region's first point (0 before the launch)."""
        points = self.shares.get(region)
        if not points or (turn is not None and turn < self.launch_turn):
            return 0.0
        first = min(points)
        if year < first:
            return (
                max(0.0, points[first] * (1 - (first - year)))
                if first > BASE_YEAR
                else points[first]
            )
        return interp(points, year)


class SubsidyRuleDef(_Frozen):
    """A sourcing rule from a month: cars whose cells come from these countries (or blocs) do
    not qualify (IRA-style, 49.5)."""

    start: str  # "YYYY-MM"
    cells_not_from: tuple[str, ...] = ()  # countries.yaml keys or blocs
    made_in: tuple[str, ...] = ()  # if listed, the car must be made in one of these
    label: str


class SubsidyDef(_Frozen):
    """A purchase subsidy (49.5): the buyer's price falls by `amount` (2010 dollars at load) for
    eligible cars in the scheme's country, from each step's month to the next."""

    key: str = Field(min_length=1)
    title: str
    region: str
    country: str  # countries.yaml key; the scheme covers its share of the region's buyers
    steps: tuple[tuple[str, float], ...]  # ("YYYY-MM", cents) amounts; 0 ends it
    price_cap: tuple[tuple[str, float], ...] = ()  # ("YYYY-MM", cents) price caps; 0 = none
    rules: tuple[SubsidyRuleDef, ...] = ()

    def amount_at(self, turn: int) -> float:
        return _step_at(self.steps, turn)

    def cap_at(self, turn: int) -> float:
        return _step_at(self.price_cap, turn)


def _step_at(steps: tuple[tuple[str, float], ...], turn: int) -> float:
    value = 0.0
    for month, v in steps:
        if month_to_turn(month) <= turn:
            value = v
    return value


class VehicleTariffDef(_Frozen):
    """A tariff on imported cars (49.5), appended to tariffs.yaml's schedules (39.3) for the
    `vehicles` good."""

    key: str = Field(min_length=1)
    title: str
    origin: str
    market: str
    steps: tuple[tuple[str, float], ...]
    tag: Literal["V", "R"]


class ApprovalDef(_Frozen):
    """A region's first approval of an autonomy level (49.4), by its automotive regulator."""

    level: Level
    month: str  # "YYYY-MM"
    label: str


class AutoRegulatorDef(_Frozen):
    """An `automotive` regulator (49.4): approves autonomy levels in its region (history to
    2025, then seeded), investigates incidents and orders recalls."""

    key: str = Field(min_length=1)
    name: str
    region: str
    approvals: tuple[ApprovalDef, ...] = ()


class VehiclesFile(_Frozen):
    regions: tuple[RegionCarsDef, ...]
    battery: BatteryDef
    cell_makers: tuple[CellMakerDef, ...]
    rivals: tuple[RivalCarsDef, ...]
    subsidies: tuple[SubsidyDef, ...]
    tariffs: tuple[VehicleTariffDef, ...]
    regulators: tuple[AutoRegulatorDef, ...]
    world_cells_gwh: dict[int, float]  # world EV battery demand, GWh a year (chain supply)
    km_per_kwh: dict[int, float]  # a typical BEV's efficiency, km a kWh (range = kWh x this)
    range_expected_km: dict[int, float]  # the market's expected range by year (feature score)
    charge_expected_kw: dict[int, float]  # the market's expected DC charging speed by year
    software_attach: dict[int, float]  # share of connected cars paying a subscription by year

    @model_validator(mode="before")
    @classmethod
    def _parse(cls, raw: Any) -> Any:
        """vehicles.yaml's tagged layout -> numbers, money in 2010 cents."""
        if not isinstance(raw, dict) or "cpi" not in raw:
            return raw
        cpi = _series(raw["cpi"])
        base = cpi[BASE_YEAR]

        def to_2010(cents: float, year: int) -> float:
            return cents * base / interp(cpi, year)

        battery = dict(raw["battery"])
        battery["pack_cents"] = {  # [value, dollar year, tag] -> 2010 cents
            int(y): to_2010(float(v[0]) * 100, int(v[1]))
            for y, v in battery.pop("pack_usd").items()
        }
        battery["cell_share"] = _series(battery["cell_share"])
        battery["lfp_share"] = _series(battery["lfp_share"])
        battery["chemistries"] = _strip(battery["chemistries"])
        regions = [
            {
                "key": key,
                "car_sales": _series(r["car_sales"]),
                "ev_share": _series(r["ev_share"]),
                "chargers": _series(r["chargers"]),
                "segments": _strip(r["segments"]),
            }
            for key, r in raw["regions"].items()
        ]
        subsidies = []
        for s in raw["subsidies"]:
            s = dict(s)
            s["steps"] = [(m, to_2010(_value(v) * 100, _year_of(m))) for m, v in s.get("steps", [])]
            s["price_cap"] = [
                (m, to_2010(_value(v) * 100, _year_of(m))) for m, v in s.get("price_cap", [])
            ]
            s.pop("source", None)
            subsidies.append(s)
        return {
            "regions": regions,
            "battery": battery,
            "cell_makers": [
                {**_strip({k: v for k, v in m.items() if k != "source"})}
                for m in raw["cell_makers"]
            ],
            "rivals": [
                _strip({k: v for k, v in r.items() if k != "source"}) for r in raw["rivals"]
            ],
            "subsidies": subsidies,
            "tariffs": [{k: v for k, v in t.items() if k != "source"} for t in raw["tariffs"]],
            "regulators": [
                {k: v for k, v in g.items() if k != "source"} for g in raw["regulators"]
            ],
            "world_cells_gwh": _series(raw["world_cells_gwh"]),
            "km_per_kwh": _series(raw["km_per_kwh"]),
            "range_expected_km": _series(raw["range_expected_km"]),
            "charge_expected_kw": _series(raw["charge_expected_kw"]),
            "software_attach": _series(raw["software_attach"]),
        }

    def region(self, key: str) -> RegionCarsDef:
        for r in self.regions:
            if r.key == key:
                return r
        raise KeyError(key)

    def rival(self, company: str) -> RivalCarsDef | None:
        return next((r for r in self.rivals if r.company == company), None)

    def cell_maker(self, key: str) -> CellMakerDef:
        for m in self.cell_makers:
            if m.key == key:
                return m
        raise KeyError(key)


# --- balance.yaml vehicles.* --------------------------------------------------------------------


class LevelDef(_Frozen):
    """An autonomy level (49.4): what it needs and what it gives."""

    label: str
    lead: float = Field(ge=0)  # autonomy lead points over the domain's baseline
    ai_quality: float = Field(ge=0)  # the company's best live ai_models quality (or bought)
    chips: dict[str, int]  # chips.types key -> chips a car
    features: float  # feature points a car gains (where approved)
    attach: float = Field(ge=0)  # share of its cars that subscribe to the level
    price_cents: int = Field(ge=0)  # the level's subscription a car a month (2010 dollars)
    incident_rate: float = Field(ge=0)  # incidents a year per 100,000 cars on the road
    approval: bool  # needs a regulator's approval in the region


class PlantBalance(_Frozen):
    """A vehicle plant (49.1) runs on the generic facility lifecycle (facility.kinds)."""

    kind: str  # facility.kinds key
    yield_range: Range  # good cars a car started: lo + (hi - lo) x mean manufacturing skill / 20


class CellPlantBalance(_Frozen):
    """An own cell plant (49.2): capacity in kWh a month, yield learning like a fab's (38.2)."""

    kind: str
    stage: int = Field(ge=0)  # company stage the build needs
    yield_start: float = Field(gt=0, le=1)
    yield_mature: float = Field(gt=0, le=1)
    learn: float = Field(gt=0)  # monthly learning at skill_ref
    skill_ref: float = Field(gt=0)
    noise_sd: float = Field(ge=0)
    other_share: float = Field(ge=0)  # other variable cost a kWh, x the month's market price
    mwh_per_kwh: float = Field(ge=0)  # power a kWh of cells
    fixed_share: float = Field(ge=0)  # fixed cost a year as a share of capex
    overrun: Range  # hidden capex overrun fraction (stream vehicles (2, facility))


class ChargingBalance(_Frozen):
    """A charging network (49.5): sites of chargers on the generic lifecycle."""

    kind: str
    kwh_per_charger_month: float = Field(gt=0)  # energy a charger sells a month at full use
    use: dict[str, float]  # region -> utilisation of an open charger
    price_cents_kwh: dict[str, float]  # region -> price a kWh sold (2010 dollars)
    exclusive_use: float = Field(ge=0, le=1)  # utilisation share kept when exclusive
    exclusive_points: float  # feature points the owner's cars gain where it is exclusive
    coverage_points: float  # feature points of fast charging at full regional coverage
    coverage_ref: float = Field(gt=0)  # public chargers per EV sold a year at full coverage
    scrutiny_share: float = Field(ge=0, le=1)  # an exclusive network's share of a region's
    # chargers above which the regulator opens a case


class SCurveBalance(_Frozen):
    """The EV share after 2025 (49.1): its logit moves `k` a year, drawn per region from `k`
    (stream vehicles (0, region)), x (1 + battery x the cut in cell price since 2025 + charging
    x coverage + subsidy x the subsidy's share of the price), capped at `cap`."""

    k: Range
    battery: float
    charging: float
    subsidy: float
    cap: float = Field(gt=0, le=1)
    floor_k: float = Field(ge=0)


class LearningBalance(_Frozen):
    """Cell prices after 2025 (49.2): learning on cumulative production plus metals."""

    rate: Range  # cost cut per doubling of cumulative EV cell production (drawn once)
    metals_share: float = Field(ge=0, le=1)  # share of the cell price that moves with metals
    floor_cents: float = Field(gt=0)  # the lowest a kWh can go (2010 dollars)


class SoftwareBalance(_Frozen):
    price_cents: dict[str, float]  # platform choice -> subscription a car a month
    attach_mult: dict[str, float]  # platform choice -> attach x this
    licence_cents: int = Field(ge=0)  # Android Automotive's licence a car (49.3)
    ota_churn_cut: float = Field(ge=0, le=1)  # an over-the-air car is replaced this much less
    platform_points: dict[str, float]  # platform choice -> feature points
    ota_features: float = Field(ge=0, le=1)  # share of later feature gains cars on the road get


class SpecBalance(_Frozen):
    """Range and charging against the market's expectation (feature points, 49.1)."""

    range_points: float  # points per 100% of range above (below) the expected
    range_cap: float  # at most this many points either way
    charge_points: float
    charge_cap: float
    pack_kwh: Range  # the pack sizes a design may choose
    charge_kw: Range
    usable: float = Field(gt=0, le=1)  # usable share of the pack


class BomBalance(_Frozen):
    """A car's bill of materials beyond the pack (49.1), 2010 dollars at index 1.0."""

    drive_cents: dict[int, float]  # motors and power electronics by year (2010 dollars)


class IncidentBalance(_Frozen):
    recall_cents: int = Field(ge=0)  # a recall's cost a car on the road (2010 dollars)
    brand_points: float = Field(ge=0)
    suspend_months: int = Field(ge=0)  # the level's approval is suspended for the company


class VehiclesBalance(_Frozen):
    start: str  # "YYYY-MM": history holds before this month (shares, prices, approvals)
    category: str  # categories.yaml key of the vehicles market
    scale: float = Field(gt=0)  # game car buyers = real x this (the devices convention)
    scale_basis: str  # where `scale` comes from (shown on the Vehicles screen)
    replacement_months: dict[str, int]  # segment -> replacement cycle (also categories.yaml)
    plant: PlantBalance
    cell_plant: CellPlantBalance
    charging: ChargingBalance
    s_curve: SCurveBalance
    learning: LearningBalance
    software: SoftwareBalance
    spec: SpecBalance
    bom: BomBalance
    levels: dict[str, LevelDef]
    incident: IncidentBalance
    domain: str  # tech_frontier.yaml key of the autonomy domain
    approval_chance: dict[str, float]  # level -> a region's chance a year of approving after 2025
    tariff_block: float = Field(ge=0, le=1)  # a rival does not enter a region at this tariff
    rival_refresh: float = Field(ge=0, le=1)  # a rival's chance a year of a model refresh (2026+)
    rival_refresh_points: float = Field(ge=0)
    rival_cash_cents: int = Field(ge=0)  # a car maker's opening capital for its car business
    history_months: int = Field(ge=1)
    energy: dict[str, int]  # action -> founder energy
    cell_good: str  # commodities.yaml key of battery cells
    unlock_year: int  # the 2012 EV era: the Vehicles screen opens (M29)

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.start)

    def level(self, key: str) -> LevelDef | None:
        return self.levels.get(key)
