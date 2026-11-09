"""Schemas for M17's tunables and data (ADR-0008, docs/formulas.md 33): `commodity.*`,
`offtake.*` and `power.*` in balance.yaml, and `commodities.yaml`, `commodities_history.yaml`,
`power_history.yaml` and `suppliers.yaml`.

Model definitions only (no file reads, no imports from the rest of the sim beyond M12a's
schemas), so `tst.sim.data_models` can import them without a cycle.

A commodity is a market good (ADR-0020 3): a key, a unit, a price history held a year at a
time with shocks placed in their months, then a seeded path. Its **index** is its price over
its 2010-2019 mean (33.1). Power is a market good by region: an index with North America 1.0.
"""

from __future__ import annotations

import itertools
import statistics
from functools import cached_property
from typing import Literal

from pydantic import Field, model_validator

from tst.sim.facilities.config import (
    FIRST_YEAR,
    MONTHS,
    TOLERANCE,
    AllocationPeriod,
    Range,
    _Frozen,
    month_to_turn,
)

LAST_YEAR = 2025  # tunable-exempt: the history runs to December 2025 (33.1)
MEAN_YEARS = (2010, 2019)  # tunable-exempt: the index's base years, 2010-2019 (33.1)
LONG_RUN_YEARS = (2015, 2025)  # tunable-exempt: the long-run level's years (33.1)
TAGS = ("V", "D", "R", "e", "A", "S")  # tunable-exempt: the dossier's source tags
YEAR_VALUE = 2  # tunable-exempt: a year is [value, tag]


# --- commodities_history.yaml and power_history.yaml -----------------------------------------


class HistoryShock(_Frozen):
    """A shock placed in its months (33.1): inside [first, last point] a month is geometric
    between the points, replacing the held annual value."""

    label: str = Field(min_length=1)
    source: str
    points: dict[str, float] = Field(min_length=2)  # tunable-exempt: two points at least

    @model_validator(mode="after")
    def _check(self) -> HistoryShock:
        turns = [month_to_turn(m) for m in self.points]
        if turns != sorted(turns) or len(set(turns)) != len(turns):
            raise ValueError(f"shock {self.label!r}: points must be in month order")
        if any(v <= 0 for v in self.points.values()):
            raise ValueError(f"shock {self.label!r}: prices must be positive")
        if self.source not in TAGS:
            raise ValueError(f"shock {self.label!r}: unknown source tag {self.source!r}")
        return self

    @cached_property
    def anchors(self) -> tuple[tuple[int, float], ...]:
        return tuple((month_to_turn(m), v) for m, v in self.points.items())

    def price_at(self, turn: int) -> float | None:
        anchors = self.anchors
        if not anchors[0][0] <= turn <= anchors[-1][0]:
            return None
        for (t0, v0), (t1, v1) in itertools.pairwise(anchors):
            if t0 <= turn <= t1:
                return float(v0 * (v1 / v0) ** ((turn - t0) / (t1 - t0)))
        return anchors[-1][1]


class AnnualHistory(_Frozen):
    """A price (or power index) held a year at a time, 2010-2025, with shocks and allocation."""

    key: str
    unit: str = "index"
    years: dict[int, tuple[float, str]]
    shocks: tuple[HistoryShock, ...] = ()
    allocation: tuple[AllocationPeriod, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _pairs(cls, value: object) -> object:
        if isinstance(value, dict) and isinstance(value.get("years"), dict):
            years = value["years"]
            value = {**value, "years": {int(k): tuple(v) for k, v in years.items()}}
        return value

    @model_validator(mode="after")
    def _check(self) -> AnnualHistory:
        missing = [y for y in range(FIRST_YEAR, LAST_YEAR + 1) if y not in self.years]
        if missing:
            raise ValueError(f"{self.key!r}: no value for {missing}")  # 33.1: rejects a gap
        extra = [y for y in self.years if not FIRST_YEAR <= y <= LAST_YEAR]
        if extra:
            raise ValueError(f"{self.key!r}: years outside 2010-2025: {extra}")
        for year, pair in self.years.items():
            if len(pair) != YEAR_VALUE or pair[0] <= 0 or pair[1] not in TAGS:
                raise ValueError(f"{self.key!r} {year}: expected [positive value, tag]")
        spans = sorted((s.anchors[0][0], s.anchors[-1][0]) for s in self.shocks)
        for (_, end), (start, _) in itertools.pairwise(spans):
            if start < end:
                raise ValueError(f"{self.key!r}: shocks overlap")
        return self

    @property
    def last_turn(self) -> int:
        return (LAST_YEAR - FIRST_YEAR + 1) * MONTHS - 1

    def value_at(self, turn: int) -> float:
        """The month's price from history: a shock's path inside its months, else the
        year's value (33.1)."""
        if not 0 <= turn <= self.last_turn:
            raise ValueError(f"turn {turn} is outside {self.key!r}'s history")
        for shock in self.shocks:
            price = shock.price_at(turn)
            if price is not None:
                return price
        return self.years[FIRST_YEAR + turn // MONTHS][0]

    def allocation_at(self, turn: int) -> float:
        for period in self.allocation:
            if month_to_turn(period.start) <= turn <= month_to_turn(period.end):
                return period.share
        return 1.0

    def shortage_start(self, turn: int) -> int | None:
        for period in self.allocation:
            if month_to_turn(period.start) <= turn <= month_to_turn(period.end):
                return month_to_turn(period.start)
        return None

    @cached_property
    def mean_2010_2019(self) -> float:
        """The index base: the 2010-2019 mean of the monthly history (33.1)."""
        lo, hi = MEAN_YEARS
        months = range((lo - FIRST_YEAR) * MONTHS, (hi - FIRST_YEAR + 1) * MONTHS)
        return statistics.fmean(self.value_at(t) for t in months)

    @cached_property
    def long_run(self) -> float:
        """The level the seeded path reverts to: the 2015-2025 median of the annual values
        (33.1; nominal, M17 decision)."""
        lo, hi = LONG_RUN_YEARS
        return float(statistics.median(self.years[y][0] for y in range(lo, hi + 1)))


class CommoditiesHistoryFile(_Frozen):
    goods: tuple[AnnualHistory, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> CommoditiesHistoryFile:
        keys = [g.key for g in self.goods]
        if len(set(keys)) != len(keys):
            raise ValueError("commodities_history.yaml: duplicate good keys")
        return self

    def good(self, key: str) -> AnnualHistory:
        for g in self.goods:
            if g.key == key:
                return g
        raise KeyError(key)


class PowerHistoryFile(_Frozen):
    regions: tuple[AnnualHistory, ...] = Field(min_length=1)

    def region(self, key: str) -> AnnualHistory:
        for r in self.regions:
            if r.key == key:
                return r
        raise KeyError(key)


# --- commodities.yaml ------------------------------------------------------------------------


class CommodityDef(_Frozen):
    key: str
    label: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    volume_unit: str = Field(min_length=1)
    usd_per_unit: float = Field(gt=0)  # dollars per volume unit for one price unit
    top_country: str = Field(min_length=1)
    top_share: float = Field(gt=0, le=1)
    share_basis: str


class CommoditiesFile(_Frozen):
    goods: tuple[CommodityDef, ...] = Field(min_length=1)

    def good(self, key: str) -> CommodityDef:
        for g in self.goods:
            if g.key == key:
                return g
        raise KeyError(key)


# --- suppliers.yaml --------------------------------------------------------------------------


class SupplierGood(_Frozen):
    share: float = Field(gt=0, le=1)
    from_month: str | None = Field(default=None, alias="from")
    until: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _from_number(cls, value: object) -> object:
        if isinstance(value, int | float):
            return {"share": value}
        return value


class SupplierRevenue(_Frozen):
    usd_m: float | None = None
    as_printed: str = Field(min_length=1)
    tag: str
    source: str = Field(min_length=1)


class SupplierDef(_Frozen):
    key: str
    name: str = Field(min_length=1)
    region: str
    listing: str = Field(min_length=1)
    goods: dict[str, SupplierGood] = Field(default_factory=dict)
    reliability: float = Field(gt=0, le=1)
    from_month: str | None = Field(default=None, alias="from")
    until: str | None = None
    revenue_2010: SupplierRevenue | None = None

    def window(self, good: str | None = None) -> tuple[int, int | None]:
        """The first and last month it can sign (the good's own window inside its own)."""
        lo = month_to_turn(self.from_month) if self.from_month else 0
        hi = month_to_turn(self.until) if self.until else None
        g = self.goods.get(good) if good else None
        if g is not None:
            if g.from_month:
                lo = max(lo, month_to_turn(g.from_month))
            if g.until:
                end = month_to_turn(g.until)
                hi = end if hi is None else min(hi, end)
        return lo, hi

    def sells(self, good: str, turn: int) -> bool:
        if good not in self.goods:
            return False
        lo, hi = self.window(good)
        return lo <= turn and (hi is None or turn <= hi)


class SuppliersFile(_Frozen):
    suppliers: tuple[SupplierDef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> SuppliersFile:
        keys = [s.key for s in self.suppliers]
        if len(set(keys)) != len(keys):
            raise ValueError("suppliers.yaml: duplicate supplier keys")
        return self

    def supplier(self, key: str) -> SupplierDef | None:
        return next((s for s in self.suppliers if s.key == key), None)


# --- balance.yaml: commodity.*, offtake.*, power.* -------------------------------------------


class CommodityShockKind(_Frozen):
    monthly: float = Field(ge=0, le=1)  # chance a month it starts (before concentration)
    concentrated_mult: float = Field(default=1.0, ge=0)  # x when top_share > ban_concentration
    rise: Range  # fraction the price rises while it runs
    allocation: Range  # allocation while it runs
    months: Range  # whole months it runs; the rise then fades over as many months


class CommodityMix(_Frozen):
    share: float = Field(ge=0, le=1)  # the commodity share of the good's cost (w, v)
    weights: dict[str, float]  # commodity -> weight, summing to 1
    # blend: (1 - share) x the good's index + share x the mix (BOMs); scale: the good's price x
    # ((1 - share) + share x the mix) (wafers), 33.2
    mode: Literal["blend", "scale"] = "blend"

    @model_validator(mode="after")
    def _check(self) -> CommodityMix:
        if abs(sum(self.weights.values()) - 1) > TOLERANCE:
            raise ValueError("a commodity mix's weights must sum to 1")
        return self


class CommodityBalance(_Frozen):
    phi: float = Field(ge=0, lt=1)  # the log-price AR(1)'s annual persistence (33.1)
    vol: dict[str, float]  # annual volatility of the log price, per good (33.1)
    semi_poly_multiple: float = Field(gt=0)  # semiconductor-grade poly = solar x this (33.1)
    ban_concentration: float = Field(gt=0, le=1)  # top share above which bans are likelier
    gap_months: int = Field(ge=0)  # months after a shock ends before another can start
    shocks: dict[str, CommodityShockKind]  # export_ban, demand_boom, supply_disruption
    mixes: dict[str, CommodityMix]  # cost good (device_bom, server_bom, foundry_wafer) -> mix
    contract_energy: int = Field(ge=0)
    contract_months: Range
    contract_take_or_pay: float = Field(ge=0, le=1)
    history_months: int = Field(gt=0)  # months of price history the API shows


class OfftakeBreach(_Frozen):
    spot_over_ceiling: float = Field(gt=1)  # a shock is severe when spot >= ceiling x this
    monthly_scale: float = Field(ge=0, le=1)  # breach chance a month = (1 - reliability) x this


class OfftakeBalance(_Frozen):
    energy: int = Field(ge=0)
    years: Range  # whole years an offtake runs (33.3: 3-10)
    collar: float = Field(ge=0, lt=1)  # floor and ceiling at the signing price x (1 -/+ this)
    prepay_max: float = Field(ge=0, le=1)  # share of year 1's value that may be prepaid
    take_or_pay: float = Field(ge=0, le=1)  # share of the contracted volume paid if not taken
    breach: OfftakeBreach


class PowerBalance(_Frozen):
    phi: float = Field(ge=0, lt=1)  # annual persistence of a region's log index after 2025
    vol: float = Field(ge=0)  # annual volatility of a region's log index after 2025
    base_region: str  # regions.yaml key held at 1.0 (North America)
    paid_by: tuple[str, ...]  # facility kinds whose operating cost is x the region's index
