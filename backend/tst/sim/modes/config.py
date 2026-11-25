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
    news_top: int = Field(ge=1)  # names from each list's top in January's news item


class SerialBalance(_Frozen):
    """Founding again after an exit (M15b addendum 10)."""

    background: str  # the scenarios.yaml start whose cap table and equity account it uses
    min_cash_dollars: int = Field(ge=0)  # the least the founder can put into the new company


class StoryBalance(_Frozen):
    """Rival CEO storylines (M15b addendum 12)."""

    feud_marks: tuple[float, ...]  # feud lines whose crossing brings a reply piece
    max_per_month: int = Field(ge=0)  # pieces a month at most


class ChallengeRule(_Frozen):
    """One challenge rule's numbers (63.2)."""

    score_mult: float = Field(gt=0)  # x the company score the result screen shows


class ChallengesBalance(_Frozen):
    """M51 (63.2): `challenges.<rule>` in balance.yaml."""

    rules: dict[str, ChallengeRule]
    hard_rivals_quality_mult: float = Field(ge=1)  # rivals' quality in their markets, x this


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
    unit: str | None = None  # M51: a team of this name (made at the start), else the root


class FabSpec(_Frozen):
    """M51: a fab the company already runs at the start (38.2), built `age_months` before it:
    live, its yield mature, its capex on the books less the depreciation since."""

    node: str  # nodes.yaml key
    region: str
    capacity: int = Field(gt=0)  # wafer starts a month (fab.sizes)
    age_months: int = Field(ge=0)
    unit: str  # the team (a StaffSpec unit) that staffs it
    country: str | None = None  # None: the region's default (countries.yaml)


class SegmentSpec(_Frozen):
    price_dollars: float = Field(ge=0)
    customers: float = Field(ge=0)


class ContractSpec(_Frozen):
    """M51: a contract-manufacturing deal running at the start (26.2), signed that month."""

    manufacturer: str  # balance.yaml hardware.contract.manufacturers key
    city: str
    units: int = Field(gt=0)  # a month
    months: int = Field(ge=1)


class ProductSpec(_Frozen):
    name: str
    category: str
    quality: float = Field(ge=0, le=100)
    features: float = Field(ge=0)  # feature points
    brand: float = Field(ge=0, le=100)
    segments: dict[str, SegmentSpec]
    # M51: a product still in development (a prototype) has no customers or launch
    status: Literal["live", "in_development"] = "live"
    contract: ContractSpec | None = None  # M51: its assembly contract at the start


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
    "arr",  # reach `arr_dollars` (M15r addendum d: the AI lab's goal, no longer era or ARR)
    "customers",  # `customers` in `category`'s `segment`
    "solvent_margin",  # cash at least 0 and a positive trailing operating margin at the end
    "unit_share",  # `share` of `category`'s customers
    "profit_no_down_round",  # an operating profit (trailing 12 months), no down round
    # M51 (63.1)
    "solvent_series",  # still solvent at the deadline, with a `series` round closed since the start
    "platform_share",  # the company's own platform holds `share` of developers in a region (44)
    "vehicles_year",  # `units` cars sold in the trailing 12 months (49)
    "fab_catch_up",  # a live fab within `node_gap` nodes of the leader, and an operating profit
    "node_volume",  # wafers run on a live fab at `node` or newer (38.2)
    # judged at the deadline: a child of the first head runs the company as its head (not a
    # professional CEO, 45.5), and the family holds control (family.control_bp, 45.6)
    "family_succession",
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
    # M15r addendum d: a bonus shown on the result screen, never a win condition: cause
    # `bonus_era` first, described by `bonus_text`
    bonus_era: str | None = None
    bonus_text: str | None = None
    series: str | None = None  # M51: a round series key (fundraising's "a", "b", ...)
    region: str | None = None  # M51: the region it must hold in (None: any one region)
    units: int | None = None  # M51: cars a year
    node: str | None = None  # M51: a nodes.yaml key
    node_gap: int | None = None  # M51: nodes behind the leading edge at most


class FamilyStartSpec(_Frozen):
    """M51: the founder's family at the start (45.1): a partner and children of these ages."""

    child_ages: tuple[int, ...] = Field(min_length=1)


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
    fabs: tuple[FabSpec, ...] = ()  # M51
    goal: GoalSpec
    deadline: tuple[int, int]  # (year, month): judged at that month's end
    # M51 (63.1): the founder and the company's home, where a scenario sets them
    founder_age: int | None = Field(default=None, ge=18)  # None: the founder's default age
    founder_region: str | None = None  # None: founder.default_region
    hq_city: str | None = None  # None: geo.default_hq_city
    family: FamilyStartSpec | None = None  # M51: built in the world's first month, then aged
    length: Literal["standard", "dynasty"] = "standard"  # M51: shown as a dynasty game (52.1)
