"""Schemas for M54's currencies (ADR-0008, ADR-0025, docs/formulas.md 64.4): `fx_history.yaml` (each
region's basket and its countries' monthly rates, 2008-2025, from FRED) and the `fx.*` keys of
balance.yaml. Model definitions only.

At load each region's **rate index** is built once, exactly: for every month from January of
`first_year` to December 2025, the sum over its basket of weight x (US dollars a unit that month /
in January 2010), from the file's decimals as written (`exact`, never a binary float), rounded half
to even to `INDEX_SCALE` (an integer: 1,000,000 is the January 2010 value). Its policy rate is the
same weights' average of its countries' rates (% a year, a float: rates are not money).
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import Range, month_to_turn
from tst.sim.money import exact

INDEX_SCALE: Final = 1_000_000  # tunable-exempt: an index of 1.0 is 10^6 (6 exact decimals)
MONTHS: Final = 12  # tunable-exempt: calendar
BASE_YEAR: Final = 2010  # tunable-exempt: ADR-0025's index base, January 2010
USD: Final = "USD"  # tunable-exempt: the game's unit (ADR-0003)

type Quote = Literal["usd_per_unit", "per_usd"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CurrencyDef(_Frozen):
    quote: Quote
    series: str
    monthly: dict[int, tuple[float, ...]]


class RateDef(_Frozen):
    series: str
    monthly: dict[int, tuple[float, ...]]


class FxRegionDef(_Frozen):
    weights: dict[str, float]
    rates: dict[str, float]


def _usd_per(c: CurrencyDef, year: int, month: int) -> Fraction:
    v = exact(c.monthly[year][month - 1])
    return v if c.quote == "usd_per_unit" else 1 / v


def build_indexes(
    raw: dict[str, Any],
) -> tuple[dict[str, tuple[int, ...]], dict[str, tuple[float, ...]]]:
    """(index by region, policy rate by region), month by month from January of first_year."""
    first = int(raw["first_year"])
    currencies = {k: CurrencyDef.model_validate(v) for k, v in raw["currencies"].items()}
    rates = {k: RateDef.model_validate(v) for k, v in raw["policy_rates"].items()}
    regions = {k: FxRegionDef.model_validate(v) for k, v in raw["regions"].items()}
    last = max(max(c.monthly) for c in currencies.values())
    index: dict[str, tuple[int, ...]] = {}
    policy: dict[str, tuple[float, ...]] = {}
    for key, region in regions.items():
        rows: list[int] = []
        prates: list[float] = []
        for year in range(first, last + 1):
            for month in range(1, MONTHS + 1):
                total = Fraction(0)
                for code, w in region.weights.items():
                    if code == USD:
                        total += exact(w)
                        continue
                    c = currencies[code]
                    total += exact(w) * _usd_per(c, year, month) / _usd_per(c, BASE_YEAR, 1)
                rows.append(round(total * INDEX_SCALE))
                prates.append(
                    sum(w * rates[cc].monthly[year][month - 1] for cc, w in region.rates.items())
                )
        index[key] = tuple(rows)
        policy[key] = tuple(prates)
    return index, policy


class FxFile(_Frozen):
    """fx_history.yaml, with each region's index and policy rate built at load (module
    docstring)."""

    first_year: int
    last_year: int
    regions: dict[str, FxRegionDef]
    index: dict[
        str, tuple[int, ...]
    ]  # region -> monthly index x INDEX_SCALE from January first_year
    policy: dict[str, tuple[float, ...]]  # region -> monthly policy rate, % a year

    @model_validator(mode="before")
    @classmethod
    def _parse(cls, raw: Any) -> Any:
        if not isinstance(raw, dict) or "currencies" not in raw:
            return raw
        index, policy = build_indexes(raw)
        last = max(max(c["monthly"]) for c in raw["currencies"].values())
        return {
            "first_year": raw["first_year"],
            "last_year": last,
            "regions": raw["regions"],
            "index": index,
            "policy": policy,
        }

    @property
    def first_turn(self) -> int:
        return (self.first_year - BASE_YEAR) * MONTHS

    @property
    def last_turn(self) -> int:
        return (self.last_year - BASE_YEAR + 1) * MONTHS - 1

    def history_index(self, region: str, turn: int) -> int:
        """The data's index in a month (held at the ends)."""
        rows = self.index[region]
        i = min(max(turn - self.first_turn, 0), len(rows) - 1)
        return rows[i]

    def history_rate(self, region: str, turn: int) -> float:
        rows = self.policy[region]
        i = min(max(turn - self.first_turn, 0), len(rows) - 1)
        return rows[i]


class FxBalance(_Frozen):
    """balance.yaml fx.* (formulas.md 64.4, ADR-0025)."""

    applies_from: str  # "YYYY-MM": rivals translate, and the indexes walk, from this month
    home: str  # the region whose currency is the US dollar (index 1 always)
    reversion: float = Field(ge=0, le=1)  # a month's pull of ln index toward ln anchor
    sigma: dict[str, float]  # region -> a month's standard deviation of ln index
    drift: dict[str, float]  # region -> the anchor's yearly drift (real rates' gap, A)
    jump_chance: float = Field(ge=0, le=1)  # a month's chance of a jump, a region
    jump_size: float = Field(ge=0, lt=1)  # a jump moves the index by +/- this share
    spread_bp: dict[str, int]  # region -> a forward's spread against the buyer
    rate_comove: float = Field(ge=0)  # a region's rate after 2025 moves this x the US's move
    term_months: Range  # a forward's term
    max_hedge_share: float = Field(gt=0, le=1)  # of the next 12 months' net exposure
    cfo_limit_share: float = Field(ge=0, le=1)  # the CFO delegate's hedge limit, of exposure
    what_if_move: float = Field(gt=0, lt=1)  # the Currency screen's dollar move
    history_months: int = Field(ge=1)  # translation months kept (the exposure screen)
    unlock_share: float = Field(ge=0, le=1)  # the Currency screen opens at this foreign share

    @property
    def start_turn(self) -> int:
        return month_to_turn(self.applies_from)
