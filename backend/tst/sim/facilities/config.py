"""Schemas for M12a's tunables and data (ADR-0008, docs/formulas.md 22): `facility.*`,
`supply.*` and `compute.*` in balance.yaml, and `components_history.yaml`.

Model definitions only (no file reads, no imports from the rest of the sim), so
`tst.sim.data_models` can import them without a cycle.

Design for v3 (ADR-0020): a facility **kind** is data (capacity unit, input good, output good,
staff, capex, life, operating cost); a **good** is data (key, unit, history, then seeded).
M12b adds assembly plants as another kind and chips as more goods; v3 adds mines, refineries,
wafer plants and fabs, and commodities.
"""

from __future__ import annotations

import itertools
import re
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

MONTH_RE: Final = re.compile(r"^(\d{4})-(\d{2})$")
FIRST_YEAR: Final = 2010  # tunable-exempt: turn 0 is January 2010 (calendar definition)
MONTHS: Final = 12  # tunable-exempt: calendar
TOLERANCE: Final = 1e-9  # tunable-exempt: float tolerance


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Range(_Frozen):
    """[lo, hi], written as a two-item list in YAML."""

    lo: float
    hi: float

    @model_validator(mode="before")
    @classmethod
    def _from_list(cls, value: object) -> object:
        if isinstance(value, list | tuple) and len(value) == 2:  # tunable-exempt: a pair
            return {"lo": value[0], "hi": value[1]}
        return value

    @model_validator(mode="after")
    def _check(self) -> Range:
        if self.lo > self.hi:
            raise ValueError("a range's lo must not exceed its hi")
        return self


def month_to_turn(text: str) -> int:
    """'2021-04' -> the turn of April 2021 (turn 0 = January 2010)."""
    match = MONTH_RE.match(text)
    if match is None:
        raise ValueError(f"expected YYYY-MM, got {text!r}")
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= MONTHS:
        raise ValueError(f"bad month in {text!r}")
    return (year - FIRST_YEAR) * MONTHS + month - 1


# --- balance.yaml: facility.* (22.2, 22.5) ---------------------------------------------------


class FacilityKindDef(_Frozen):
    """One facility kind (ADR-0020 2): its unit, input and output goods and economics."""

    label: str = Field(min_length=1)
    unit: str = Field(min_length=1)  # capacity unit, e.g. "CU"
    input_good: str  # the market good whose index prices capex (supply.goods)
    output_good: str  # what a unit of capacity produces (compute.goods)
    capex_per_unit_cents: int = Field(gt=0)  # 2010 dollars, x the input good's index
    build_months: int = Field(gt=0)
    opex_per_unit_cents: int = Field(ge=0)  # a month, per live unit
    life_months: int = Field(gt=0)  # straight-line depreciation from completion
    staff_per: float = Field(gt=0)  # capacity units per staff member needed
    staff_roles: tuple[str, ...] = Field(min_length=1)  # roles.yaml keys that count as staff
    staff_skill: str  # skills.yaml key whose mean sets reliability
    # M12b (26.2): an assembly plant's fixed cost a live month and cost per unit run; the
    # capacities a build may choose (None: facility.sizes); whether it has outages (22.5)
    fixed_opex_cents: int = Field(default=0, ge=0)
    variable_cents: int = Field(default=0, ge=0)
    sizes: tuple[int, ...] | None = None
    outages: bool = True


class OutageBalance(_Frozen):
    base: float = Field(ge=0, le=1)  # chance a month x (100 - reliability) / 10 (22.5)
    customers_share: float = Field(ge=0, le=1)  # share of the critical customers_pct cap lost
    cloud_churn_mult: float = Field(ge=1)  # cloud customers' churn x this in the outage month


class FacilityBalance(_Frozen):
    kinds: dict[str, FacilityKindDef] = Field(min_length=1)
    sizes: tuple[int, ...] = Field(min_length=1)  # capacities a build may choose
    build_energy: int = Field(ge=0)
    close_energy: int = Field(ge=0)
    assign_energy: int = Field(ge=0)
    sale_share: float = Field(ge=0, le=1)  # of book value, when sold
    reliability_floor: float = Field(ge=0, le=1)  # rel = 100 c (floor + skill_weight s / 20)
    reliability_skill: float = Field(ge=0, le=1)
    outage: OutageBalance

    @model_validator(mode="after")
    def _check(self) -> FacilityBalance:
        total = self.reliability_floor + self.reliability_skill
        if abs(total - 1) > TOLERANCE:
            raise ValueError("reliability_floor + reliability_skill must be 1")
        return self


# --- balance.yaml: supply.* (22.4) -----------------------------------------------------------


class Ar1Change(_Frozen):
    """A good's yearly change after its history: g' = mean + phi (g - mean) + N(0, sd)."""

    mean: float
    phi: float = Field(ge=0, le=1)
    shock_sd: float = Field(ge=0)
    bounds: Range


class ShockBalance(_Frozen):
    monthly: float = Field(ge=0, le=1)  # chance a shock starts in a month
    gap_months: int = Field(ge=0)  # months since the last shock began before another can
    rise: Range  # fraction the index rises
    allocation: Range  # allocation while it lasts (fraction)
    months: Range  # how long it lasts (whole months)


class SupplyBalance(_Frozen):
    change: Ar1Change
    shock: ShockBalance
    delay_step: float = Field(gt=0, le=1)  # one month late for each this much shortfall
    contract_energy: int = Field(ge=0)
    contract_months: Range  # a contract's term, whole months
    take_or_pay: float = Field(ge=0, le=1)  # share of an unused volume's value charged
    history_months: int = Field(gt=0)  # months of index history the API shows


# --- balance.yaml: compute.* (22.1, 22.3) ----------------------------------------------------


class ComputeGoodDef(_Frozen):
    """A compute good: what one unit costs on spot at index 1.0."""

    label: str = Field(min_length=1)
    spot_cents: int = Field(gt=0)  # a unit a month at index 1.0 (one CU = $1,000)
    spot_index: str  # "flat" (always 1.0) or "ai" (M10's AI compute index, 20.1)


class ComputeBalance(_Frozen):
    goods: dict[str, ComputeGoodDef] = Field(min_length=1)
    indexed_good: str  # the good a compute_indexed category's products need (AI)
    plain_good: str  # the good every other category's products need
    feature_base: float = Field(ge=0)  # cloud features = base + per_lead x lead, capped
    feature_per_lead: float = Field(ge=0)
    capacity_category: str  # categories.yaml key of the market that sells spare capacity

    @model_validator(mode="after")
    def _check(self) -> ComputeBalance:
        for good in (self.indexed_good, self.plain_good):
            if good not in self.goods:
                raise ValueError(f"compute good {good!r} is not in compute.goods")
        for key, spec in self.goods.items():
            if spec.spot_index not in ("flat", "ai"):
                raise ValueError(f"compute.goods.{key}.spot_index must be flat or ai")
        return self


# --- components_history.yaml (22.4) ----------------------------------------------------------


class AllocationPeriod(_Frozen):
    start: str  # YYYY-MM, first month
    end: str  # YYYY-MM, last month
    share: float = Field(gt=0, le=1)
    # M12b (26.3): only advanced-node buyers (chips.types advanced_node) are short
    advanced_only: bool = False

    @model_validator(mode="after")
    def _check(self) -> AllocationPeriod:
        if month_to_turn(self.end) < month_to_turn(self.start):
            raise ValueError("an allocation period must end after it starts")
        return self


class GoodHistory(_Frozen):
    """A market good's index history (ADR-0020 3): anchor months with geometric
    interpolation between them, and allocation periods (100% outside them)."""

    key: str
    label: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    points: dict[str, float] = Field(min_length=2)  # tunable-exempt: two anchors at least
    allocation: tuple[AllocationPeriod, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> GoodHistory:
        turns = [month_to_turn(m) for m in self.points]
        if turns != sorted(turns) or len(set(turns)) != len(turns):
            raise ValueError(f"good {self.key!r}: points must be in month order")
        if turns[0] != 0:
            raise ValueError(f"good {self.key!r}: the first point must be 2010-01")
        if any(v <= 0 for v in self.points.values()):
            raise ValueError(f"good {self.key!r}: index values must be positive")
        return self

    @property
    def last_turn(self) -> int:
        return max(month_to_turn(m) for m in self.points)

    def index_at(self, turn: int) -> float:
        """The index in `turn` (within the history): geometric between anchors."""
        anchors = sorted((month_to_turn(m), v) for m, v in self.points.items())
        if not 0 <= turn <= anchors[-1][0]:
            raise ValueError(f"turn {turn} is outside {self.key!r}'s history")
        for (t0, v0), (t1, v1) in itertools.pairwise(anchors):
            if t0 <= turn <= t1:
                return float(v0 * (v1 / v0) ** ((turn - t0) / (t1 - t0)))
        return anchors[-1][1]

    def allocation_at(self, turn: int, *, advanced: bool = False) -> float:
        """The share delivered on time in `turn`; periods marked advanced_only bind only
        advanced-node buyers (M12b, 26.3)."""
        for period in self.allocation:
            if period.advanced_only and not advanced:
                continue
            if month_to_turn(period.start) <= turn <= month_to_turn(period.end):
                return period.share
        return 1.0

    def shortage_start(self, turn: int, *, advanced: bool = False) -> int | None:
        """The first month of the shortage running in `turn`, if any (M12b, 26.2)."""
        for period in self.allocation:
            if period.advanced_only and not advanced:
                continue
            if month_to_turn(period.start) <= turn <= month_to_turn(period.end):
                return month_to_turn(period.start)
        return None


class ComponentsHistoryFile(_Frozen):
    goods: tuple[GoodHistory, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> ComponentsHistoryFile:
        keys = [g.key for g in self.goods]
        if len(set(keys)) != len(keys):
            raise ValueError("components_history.yaml: duplicate good keys")
        if len({g.last_turn for g in self.goods}) != 1:
            raise ValueError("components_history.yaml: every good's history must end together")
        return self

    def good(self, key: str) -> GoodHistory:
        for g in self.goods:
            if g.key == key:
                return g
        raise KeyError(key)

    @property
    def last_turn(self) -> int:
        return self.goods[0].last_turn

    def index_of(self, key: str) -> int:
        """The good's position: the `supply` stream key (ADR-0013)."""
        return [g.key for g in self.goods].index(key)
