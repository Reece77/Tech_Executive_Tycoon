"""Schemas for M15b's tunables (ADR-0008, docs/formulas.md 30.1-30.5): `score.*`, `rank.*`
and `sandbox.*` in balance.yaml. Model definitions only, so `tst.sim.data_models` can import
them without a cycle."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ScoreBalance(_Frozen):
    """The company score (30.1)."""

    value_floor_dollars: float = Field(gt=0)  # V at or below this scores 0
    value_span_decades: float = Field(gt=0)  # decades above the floor to the full value part
    weight_value: float = Field(ge=0)
    weight_growth: float = Field(ge=0)
    weight_profit: float = Field(ge=0)
    weight_leadership: float = Field(ge=0)
    weight_reputation: float = Field(ge=0)
    growth_full: float = Field(gt=0)  # 3-year revenue CAGR scoring the full growth part
    margin_floor: float  # trailing operating margin scoring 0
    margin_span: float = Field(gt=0)  # margin above the floor to score the full part
    reputation_span: float = Field(gt=0)  # brand + credibility points for the full part


class RankWeights(_Frozen):
    """How one list ranks companies: weights on its normalised measures."""

    first: float = Field(ge=0)
    second: float = Field(ge=0)
    third: float = Field(ge=0)


class RankBalance(_Frozen):
    """Industry rankings each January (30.4)."""

    top_revenue: int = Field(ge=1)  # places in the Top 50 by revenue
    top_lists: int = Field(ge=1)  # places in Best places to work and Most innovative
    places_min_staff: int = Field(ge=0)  # companies this size or more enter Best places to work
    effect_places: int = Field(ge=1)  # a place this high or better earns the list's effect
    hiring: float = Field(ge=0)  # hiring appeal for a year from a top Best places to work
    brand: float = Field(ge=0)  # brand target points for a year from a top Most innovative
    effect_months: int = Field(ge=1)
    years: int = Field(ge=1)  # Most innovative counts eras caused and launches over these years
    tenure_full_months: int = Field(ge=1)  # mean tenure scoring the full tenure measure
    places: RankWeights  # morale, pay against market, tenure
    innovative: RankWeights  # research leads, eras caused, launches
    lead_full: float = Field(gt=0)  # summed research lead scoring the full lead measure
    eras_full: int = Field(ge=1)
    launches_full: int = Field(ge=1)


class SandboxBalance(_Frozen):
    """Sandbox starts (30.2)."""

    years: tuple[int, int]  # the first and last start year offered
    cash_dollars: tuple[int, int]  # the starting cash range offered
    rival_share_half: float = Field(gt=0, lt=1)  # "half the rivals": the share kept
    era_spread_months: int = Field(ge=1)  # "all seeded": a historical era's window +- this

    @model_validator(mode="after")
    def _ordered(self) -> SandboxBalance:
        if self.years[0] > self.years[1] or self.cash_dollars[0] > self.cash_dollars[1]:
            raise ValueError("sandbox ranges must be (low, high)")
        return self


# --- Historical scenarios (30.3; data in scenarios.yaml's `historical`) --------------------


class StaffSpec(_Frozen):
    role: str
    level: str
    count: int = Field(ge=1)


class SegmentSpec(_Frozen):
    price_dollars: float = Field(ge=0)
    customers: float = Field(ge=0)


class ProductSpec(_Frozen):
    name: str
    category: str
    quality: float = Field(ge=0, le=100)
    features: float = Field(ge=0)  # feature points
    brand: float = Field(ge=0, le=100)
    segments: dict[str, SegmentSpec]


class LeadSpec(_Frozen):
    domain: str
    lead: float = Field(ge=0)


class LoanSpec(_Frozen):
    lender: str  # investors.yaml lenders key
    principal_dollars: int = Field(gt=0)
    rate_bp: int = Field(ge=0)
    term_months: int = Field(ge=1)
    interest_only_months: int = Field(ge=0)


type GoalKind = Literal[
    "era_or_arr",  # cause `era` first, or reach `arr_dollars`
    "customers",  # `customers` in `category`'s `segment`
    "solvent_margin",  # cash at least 0 and a positive trailing operating margin at the end
    "unit_share",  # `share` of `category`'s customers
    "profit_no_down_round",  # an operating profit (trailing 12 months), no down round
]


class GoalSpec(_Frozen):
    kind: GoalKind
    text: str  # the goal in words, for the New game and result screens
    era: str | None = None
    arr_dollars: int | None = None
    category: str | None = None
    segment: str | None = None
    customers: int | None = None
    share: float | None = None


class HistoricalScenario(_Frozen):
    """One historical scenario (30.3): a start and a goal with a deadline."""

    key: str
    label: str
    description: str
    year: int
    background: str  # a scenarios.yaml start: cap table and equity account
    cash_dollars: int = Field(ge=0)
    stage: int = Field(ge=0, le=5)  # tunable-exempt: the stage scale is 0-5
    staff: tuple[StaffSpec, ...] = ()
    products: tuple[ProductSpec, ...] = ()
    research: tuple[LeadSpec, ...] = ()
    loans: tuple[LoanSpec, ...] = ()
    goal: GoalSpec
    deadline: tuple[int, int]  # (year, month): judged at that month's end
