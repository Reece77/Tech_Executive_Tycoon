"""Schemas for M32's data and tunables (ADR-0008, docs/formulas.md 46, ADR-0022): `power.yaml`
and the `power.*` keys balance.yaml gains in M32 (M17's `phi`, `vol`, `base_region` and
`paid_by` stay in `tst.sim.commodities.config.PowerBalance`, which nests these).

Every value in power.yaml carries its tag and source; these models keep the numbers and drop the
tags, converting money to 2010 dollars (`cpi`, `fx`) once, at load. Model definitions only (no
file reads), so `tst.sim.data_models` can import them without a cycle.
"""

from __future__ import annotations

import itertools
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.calendar import from_2010

PLANT_TYPES: Final = ("gas", "solar_storage", "wind", "nuclear", "smr")
type PlantType = Literal["gas", "solar_storage", "wind", "nuclear", "smr"]
BASE_YEAR: Final = 2010  # tunable-exempt: the game's money is in 2010 dollars
ALL: Final = "all"  # tunable-exempt: a capacity factor for every region
FUELLED: Final = ("gas",)  # tunable-exempt: types whose fuel is the region's gas
TECHS: Final = ("coal", "gas", "nuclear", "hydro", "wind", "solar", "other")
KILO: Final = 1000  # tunable-exempt: Btu/kWh = MMBtu/MWh x 1,000; kg a tonne
MIX_TOLERANCE: Final = 1e-6  # tunable-exempt: a producer's mix shares add to 1


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def interp(points: dict[int, float], year: float) -> float:
    """Linear between year points, held at the ends; from 2010 without 2008-2009 (M50)."""
    pts = sorted(from_2010(points, year).items())
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


# --- power.yaml --------------------------------------------------------------------------------


class PlantTypeDef(_Frozen):
    """A plant type (46.2) with its money in 2010 dollars."""

    key: PlantType
    label: str
    capex_kw: dict[int, float]  # $/kW overnight by build year (2010 dollars)
    build_months: int = Field(ge=1)
    capacity_factor: dict[str, float]  # region (or "all") -> share of the year at full power
    fixed_om_kw: dict[int, float]  # $/kW-year (2010 dollars)
    variable_om_mwh: dict[int, float]  # $/MWh (2010 dollars)
    heat_rate: dict[int, float] = Field(default_factory=dict)  # Btu/kWh (gas)
    carbon_kg_per_mmbtu: float = 0.0
    fuel_mwh: float = 0.0  # $/MWh of fuel for nuclear types (2010 dollars)
    life_years: int = Field(ge=1)
    era: tuple[int, int] | None = None  # SMR: the first orderable year is drawn in this range

    def cf(self, region: str) -> float:
        return self.capacity_factor.get(region, self.capacity_factor.get(ALL, 0.0))

    def capex_at(self, year: float) -> float:
        return interp(self.capex_kw, year)

    def fixed_om_at(self, year: float) -> float:
        return interp(self.fixed_om_kw, year)

    def variable_om_at(self, year: float) -> float:
        return interp(self.variable_om_mwh, year) if self.variable_om_mwh else 0.0

    def heat_rate_at(self, year: float) -> float:
        return interp(self.heat_rate, year) if self.heat_rate else 0.0

    def intensity_at(self, year: float) -> float:
        """Direct tCO2 a MWh: heat rate (Btu/kWh = MMBtu/MWh x 1,000) x kg CO2 a MMBtu."""
        return self.heat_rate_at(year) / KILO * self.carbon_kg_per_mmbtu / KILO


class RegionPowerDef(_Frozen):
    """A region's power data (46.2-46.5), money in 2010 dollars."""

    key: str
    gas: dict[int, float]  # $/MMBtu (2010 dollars)
    generation_twh: dict[int, float]
    grid_intensity: dict[int, float]  # tCO2 a MWh
    carbon: dict[int, float]  # $/t (2010 dollars) from the scheme's start; empty = none
    queue_months: dict[int, float]
    outages_a_year: float = Field(ge=0)
    demand_growth: float

    def carbon_at(self, year: int) -> float:
        """The year's carbon price to 2025: the data's, 0 before the scheme's first year, the
        last year's after it."""
        if not self.carbon or year < min(self.carbon):
            return 0.0
        return self.carbon[max(y for y in self.carbon if y <= year)]


class ProducerDef(_Frozen):
    """A power producer (46.7): a chain company of the region's power good."""

    key: str = Field(min_length=1)
    name: str
    country: str
    gw: float = Field(gt=0)
    personality: Literal["aggressive", "premium", "fast_follower", "cost_leader"]
    cost: float = Field(ge=0, le=1)
    mix: dict[str, float]
    tag: str = ""


class OtherGeneratorsDef(_Frozen):
    cost: float = Field(ge=0, le=1)
    country: str


class PowerFile(_Frozen):
    plant_types: tuple[PlantTypeDef, ...]
    regions: tuple[RegionPowerDef, ...]
    draws: dict[str, float]  # facility kind -> MWh a live unit-month
    fleet_capacity_factor: dict[str, float]
    producers: tuple[ProducerDef, ...]
    others: dict[str, OtherGeneratorsDef]
    build_months: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def _parse(cls, raw: Any) -> Any:
        """power.yaml's tagged layout -> the models' numbers in 2010 dollars."""
        if not isinstance(raw, dict) or "cpi" not in raw:
            return raw
        cpi = {int(y): float(v) for y, v in raw["cpi"].items()}
        fx = {k: {int(y): float(v) for y, v in pts.items()} for k, pts in raw["fx"].items()}
        base = cpi[BASE_YEAR]

        def real(value: float, year: int) -> float:
            return value * base / interp({y: v for y, v in cpi.items()}, year)

        def money(points: dict[Any, Any]) -> dict[int, float]:
            return {int(y): real(float(p[0]), int(p[1])) for y, p in points.items()}

        def nums(points: dict[Any, Any]) -> dict[int, float]:
            return {int(y): _value(p) for y, p in points.items()}

        types = []
        for t in raw["plant_types"]:
            fuel = t.get("fuel_mwh")
            types.append(
                {
                    "key": t["key"],
                    "label": t["label"],
                    "capex_kw": money(t["capex"]),
                    "build_months": int(_value(t["build_months"])),
                    "capacity_factor": {r: _value(v) for r, v in t["capacity_factor"].items()},
                    "fixed_om_kw": money(t["fixed_om"]),
                    "variable_om_mwh": money(t.get("variable_om", {})),
                    "heat_rate": nums(t.get("heat_rate", {})),
                    "carbon_kg_per_mmbtu": _value(t.get("carbon_kg_per_mmbtu", 0.0)),
                    "fuel_mwh": real(float(fuel[0]), int(fuel[1])) if fuel else 0.0,
                    "life_years": int(_value(t["life_years"])),
                    "era": (int(t["era"][0]), int(t["era"][1])) if "era" in t else None,
                }
            )
        regions = []
        for r in raw["regions"]:
            currency, prices = r["carbon"]
            rate = fx[currency]
            carbon = {
                int(y): real(float(p) / interp(rate, int(y)), int(y)) for y, p in prices.items()
            }
            regions.append(
                {
                    "key": r["key"],
                    "gas": {int(y): real(float(v), int(y)) for y, v in r["gas"].items()},
                    "generation_twh": {int(y): float(v) for y, v in r["generation"].items()},
                    "grid_intensity": {int(y): float(v) for y, v in r["grid_intensity"].items()},
                    "carbon": carbon,
                    "queue_months": {int(y): float(v) for y, v in r["queue_months"].items()},
                    "outages_a_year": _value(r["outages_a_year"]),
                    "demand_growth": _value(r["demand_growth"]),
                }
            )
        return {
            "plant_types": types,
            "regions": regions,
            "draws": {k: _value(v) for k, v in raw["draws"].items()},
            "fleet_capacity_factor": raw["fleet_capacity_factor"],
            "producers": raw["producers"],
            "others": raw["others"],
            "build_months": int(_value(raw["build_months"])),
        }

    @model_validator(mode="after")
    def _check(self) -> PowerFile:
        if tuple(t.key for t in self.plant_types) != PLANT_TYPES:
            raise ValueError(f"power.yaml: plant_types must be {PLANT_TYPES} in order")
        keys = [p.key for p in self.producers]
        if len(set(keys)) != len(keys):
            raise ValueError("power.yaml: duplicate producer keys")
        for p in self.producers:
            if abs(sum(p.mix.values()) - 1) > MIX_TOLERANCE or set(p.mix) - set(TECHS):
                raise ValueError(f"power.yaml: producer {p.key}'s mix must be shares of {TECHS}")
        for r in self.regions:
            if not r.gas or not r.generation_twh or not r.grid_intensity or not r.queue_months:
                raise ValueError(f"power.yaml: region {r.key} lacks a series")
        if set(self.fleet_capacity_factor) != set(TECHS):
            raise ValueError("power.yaml: fleet_capacity_factor needs every technology")
        return self

    def plant_type(self, key: str) -> PlantTypeDef:
        return next(t for t in self.plant_types if t.key == key)

    def region(self, key: str) -> RegionPowerDef:
        return next(r for r in self.regions if r.key == key)

    def has_region(self, key: str) -> bool:
        return any(r.key == key for r in self.regions)


# --- balance.yaml power.* (M32) ----------------------------------------------------------------


class Span(_Frozen):
    lo: float
    hi: float

    @model_validator(mode="before")
    @classmethod
    def _pair(cls, raw: Any) -> Any:
        if isinstance(raw, list | tuple):
            return {"lo": raw[0], "hi": raw[1]}
        return raw

    @model_validator(mode="after")
    def _order(self) -> Span:
        if self.lo > self.hi:
            raise ValueError("a span's lo is above its hi")
        return self


class PlantBalance(_Frozen):
    """Owned plants (46.2)."""

    min_stage: int = Field(ge=1)  # owned plants unlock at this company stage (a one-off)
    energy: int = Field(ge=0)  # founder energy to order a plant
    sizes_mw: tuple[float, ...] = Field(min_length=1)  # MW a plant order may choose
    overrun: dict[str, Span]  # type -> the hidden capex overrun's range (fraction)
    overrun_skew: float = Field(ge=1)  # overrun = lo + (hi - lo) x u ^ skew
    overrun_delay: dict[str, float]  # type -> build months x (1 + overrun x this)
    learning: dict[str, Span]  # type -> yearly capex decline after 2025 (seeded per game)
    discount_rate: float = Field(gt=0, lt=1)  # a year: levelised cost and the IRR's hurdle
    outages_a_year: dict[str, float]  # type -> forced outages a year
    outage_months: dict[str, Span]  # type -> months a forced outage lasts (whole)
    load_share: dict[str, float]  # type -> share of a load it can supply in a month (its hours)
    firm_share: dict[str, float]  # type -> share of its rating it holds through a grid outage
    smr_start: str  # the month the SMR era's draw is made (the last history month's next)
    capex_premium: float = Field(ge=1)  # an owner's site works and connection over the quote
    gas_adder: float = Field(ge=0)  # $/MMBtu (2010 dollars) a site pays over the regional price


class PpaBalance(_Frozen):
    """Power-purchase agreements (46.2)."""

    energy: int = Field(ge=0)
    years: Span  # whole years a PPA runs (46.2: 5-20)
    discount_per_year: float = Field(ge=0, lt=1)  # the price under the forward, x each year of term
    max_discount: float = Field(ge=0, lt=1)
    take_or_pay: float = Field(ge=0, le=1)  # share of untaken volume still paid (33.3)
    max_share: float = Field(gt=0)  # a PPA's volume at most this x the company's regional demand


class QueueBalance(_Frozen):
    """Grid queues (46.3)."""

    min_mw: float = Field(ge=0)  # a data centre or fab above this joins its region's queue
    min_share: float = Field(ge=0, lt=1)  # no connection before this x the wait
    shown: Span  # the range the screen shows: the wait x lo .. x hi
    growth: float = Field(ge=0)  # after 2025 the wait grows by this x the region's load growth
    sd: float = Field(ge=0)  # yearly log-sd of the wait after 2025
    floor_months: float = Field(ge=0)
    cap_months: float = Field(gt=0)


class CarbonBalance(_Frozen):
    """Carbon prices after 2025 (46.4): a yearly seeded path with policy steps."""

    drift: dict[str, float]  # region -> mean yearly log change of an existing price
    sd: float = Field(ge=0)
    start_rate: dict[str, float]  # region -> chance a year a region without a price starts one
    start_price: Span  # $/t (2010 dollars) a new scheme opens at
    step_rate: float = Field(ge=0, le=1)  # chance a year of a policy step where a price exists
    step: Span  # a step's size: the price x (1 + this)
    decarbonise: dict[str, float]  # region -> the grid's yearly fall in intensity after 2025
    decarbonise_sd: float = Field(ge=0)
    pass_through: float = Field(ge=0, le=1)  # share of a carbon change the grid price carries
    green_brand_tonnes: float = Field(ge=0)  # tCO2 a $1M revenue above which brands react
    clean_share: float = Field(ge=0, le=1)  # clean energy share above which brand +1
    brand_hit: Span  # consumer brands' fall above the threshold (46.4: -1 to -3)
    beloved_hit: float  # a Beloved brand's fall


class OutageBalance(_Frozen):
    """Grid and plant outages (46.5)."""

    wafer_loss: float = Field(ge=0, le=1)  # a fab loses this x the month's starts in a grid outage
    tight_factor: float = Field(ge=0)  # outages x (1 + this x (factor - 1)) in a tight market
    max_rate: float = Field(gt=0)  # a region's grid outages a year at most


class RivalPowerBalance(_Frozen):
    """Rivals' power (46.7): rival foundries' PPAs and plants each December from power.start."""

    mwh_per_wafer: float = Field(gt=0)  # a rival foundry's energy a wafer start
    ppa_share: dict[str, float]  # personality -> share of its load it keeps under PPAs
    ppa_years: int = Field(ge=1)
    plant_rate: dict[str, float]  # personality -> chance a December it builds a plant
    plant_share: float = Field(ge=0, le=1)  # a rival plant's energy x its load
    plant_cost: float = Field(ge=0, le=1)  # a rival plant's position on the cost curve


class PowerExtraBalance(_Frozen):
    """M32's power.* keys (formulas.md 46)."""

    start: str  # queues, grid outages, carbon pass-through and producers from this month
    standby_share: float = Field(ge=0, le=1)  # of the grid price, on behind-the-meter energy
    grid_charge_share: float = Field(ge=0, le=1)  # of the grid price, paid on own energy off-site
    export_discount: float = Field(ge=0, le=1)  # surplus sells at the grid price x (1 - this)
    hours_a_month: float = Field(gt=0)
    plants: PlantBalance
    ppa: PpaBalance
    queue: QueueBalance
    carbon: CarbonBalance
    outage: OutageBalance
    rivals: RivalPowerBalance
    history_months: int = Field(ge=1)  # months of a company's power history kept
