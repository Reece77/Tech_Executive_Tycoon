"""Schema for M19's data (ADR-0008, docs/formulas.md 35): `mining.*` in balance.yaml and
nationalization_history.yaml. Model definitions only (no imports from the rest of the sim), so
`tst.sim.data_models` can import them without a cycle."""

from __future__ import annotations

import re
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SUBTYPES: Final = ("open_pit", "underground", "brine")  # 35.2
SAFETY: Final = ("low", "normal", "high")  # a mine's safety spend
MONTH_RE: Final = re.compile(r"^(\d{4})-(\d{2})$")
FIRST_YEAR: Final = 2010  # tunable-exempt: turn 0 is January 2010 (calendar definition)
MONTHS: Final = 12  # tunable-exempt: calendar

type Subtype = Literal["open_pit", "underground", "brine"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def month_to_turn(text: str) -> int:
    match = MONTH_RE.match(text)
    if match is None:
        raise ValueError(f"{text!r} is not YYYY-MM")
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= MONTHS:
        raise ValueError(f"{text!r} has no month {month}")
    return (year - FIRST_YEAR) * MONTHS + month - 1


class Span(_Frozen):
    """A closed range [lo, hi]; written as a two-item list in YAML."""

    lo: float
    hi: float

    @model_validator(mode="before")
    @classmethod
    def _from_list(cls, value: object) -> object:
        if isinstance(value, list | tuple) and len(value) == 2:  # tunable-exempt: a pair
            return {"lo": value[0], "hi": value[1]}
        return value

    @model_validator(mode="after")
    def _check(self) -> Span:
        if self.lo > self.hi:
            raise ValueError(f"range low {self.lo} is above high {self.hi}")
        return self


class SubtypeBalance(_Frozen):
    """One mine subtype (35.2): construction, ramp, cost split and accident rate."""

    label: str = Field(min_length=1)
    construction_months: Span  # drawn on stream mining at the build order (whole months)
    ramp: tuple[float, ...] = Field(min_length=1)  # share of capacity in production years 1..n
    accident_base: float = Field(ge=0, le=1)  # chance a mine-year at average safety
    fixed_share: float = Field(ge=0, le=1)  # of the operating cost a tonne at capacity
    opex_mult: float = Field(gt=0)  # x the deposit's operating cost a t of ore

    @model_validator(mode="after")
    def _check(self) -> SubtypeBalance:
        if any(not 0 < r <= 1 for r in self.ramp) or self.ramp[-1] != 1:
            raise ValueError("a ramp's shares are in (0, 1] and end at 1")
        if list(self.ramp) != sorted(self.ramp):
            raise ValueError("a ramp never falls")
        return self


class AccidentBalance(_Frozen):
    """35.4: chance a month = base / 12 x f(s, c) / f(skill_ref, 1) x safety factor, with
    f(s, c) = max(floor, skill_base - skill_slope x s) x max(floor, cover_base - c)."""

    skill_base: float = Field(gt=0)
    skill_slope: float = Field(ge=0)
    cover_base: float = Field(gt=0)
    floor: float = Field(gt=0)
    skill_ref: float = Field(ge=1, le=20)  # tunable-exempt: the attribute scale
    safety_factor: dict[str, float]  # by safety level
    safety_cost: dict[str, float]  # x the mine's fixed cost
    fine_cents: int = Field(ge=0)  # always
    stop_months: int = Field(ge=0)  # investigate: months of lost output
    stop_fine_share: float = Field(ge=0)  # investigate: x the fine
    compensate_cents: int = Field(ge=0)
    beloved: float = Field(ge=0)
    ruthless: float = Field(ge=0)
    contest_risk: float = Field(ge=0, le=1)  # contest: chance of a court ruling against
    contest_fine_mult: float = Field(ge=0)  # ... x the fine
    brand_hit: float = Field(ge=0)  # brand points off the group's products
    credibility_hit: float = Field(ge=0)

    @model_validator(mode="after")
    def _check(self) -> AccidentBalance:
        for name, table in (
            ("safety_factor", self.safety_factor),
            ("safety_cost", self.safety_cost),
        ):
            if set(table) != set(SAFETY):
                raise ValueError(f"mining.accident.{name} needs {list(SAFETY)}")
        return self


class NationalizationBalance(_Frozen):
    """35.4: after 2025, a (region, commodity) event's chance a month is
    monthly_base x the region's resource_nationalism x the commodity's strategic weight."""

    monthly_base: float = Field(ge=0, le=1)
    ban_share: float = Field(ge=0, le=1)  # of seeded events, export bans (the rest: takeovers)
    ban_months: Span
    ban_price_share: float = Field(ge=0, le=1)  # spot price the mine gets inside its region
    partner_share: Span  # a state partner's stake (fraction)
    sell_out_share: float = Field(ge=0, le=1)  # of book value, selling to the state
    arbitration_months: Span
    arbitration_legal_cents: int = Field(ge=0)  # a month while it runs
    award_win: float = Field(ge=0, le=1)
    award_share: Span  # of book value at seizure, when the award goes the company's way
    rival_cut: float = Field(ge=0, le=1)  # a rival's capacity in the region falls by this


class CrashBalance(_Frozen):
    months_below: int = Field(ge=1)  # price under all-in cost this many months running
    care_fixed: float = Field(ge=0, le=1)  # care and maintenance: fixed cost x this
    restart_months: int = Field(ge=0)
    restart_cents_per_kt: int = Field(ge=0)  # restart cost a thousand t of capacity
    hedge_share: float = Field(ge=0, le=1)  # the hedge: an offtake on this share of capacity
    hedge_years: int = Field(ge=1)


class SaleBalance(_Frozen):
    contract_months: Span  # a seller's fixed-price contract
    offtake_years: Span
    collar: float = Field(ge=0, le=1)  # an offtake's floor and ceiling around the price


class RivalMinersBalance(_Frozen):
    """35.5: a supplier's abstract capacity per region follows prices with a lag."""

    lag_months: int = Field(ge=0)
    spike: float = Field(gt=1)  # the price index this much above 1.0 for a year: expand
    expand: float = Field(ge=0)
    crash: float = Field(gt=0, lt=1)  # below this: cut
    cut: float = Field(ge=0, le=1)
    floor: float = Field(gt=0)  # capacity never below this share of its start
    cap: float = Field(gt=1)
    buy_share: float = Field(ge=0)  # a rival's bid for a permitted project, x its sale price
    buy_monthly: float = Field(ge=0, le=1)  # chance a month a rival bids for one
    mine_bid: float = Field(ge=0)  # a bid for an operating mine, x its book value


class FoundBalance(_Frozen):
    energy: int = Field(ge=0)
    min_stage: int = Field(ge=0)
    min_cents: int = Field(ge=0)


class MiningBalance(_Frozen):
    found: FoundBalance  # 35.1
    build_energy: int = Field(ge=0)
    close_energy: int = Field(ge=0)
    care_energy: int = Field(ge=0)
    sale_energy: int = Field(ge=0)
    capacity_range: Span  # x the study's design capacity
    capex_scale: float = Field(gt=0, le=1)  # capex x (capacity / design) ** this
    overrun: dict[str, Span]  # by study level (fraction over the estimate)
    reveal_at: float = Field(gt=0, lt=1)  # share of construction when the cost is revised
    underground_depth_m: float = Field(gt=0)  # hard rock deeper than this is mined underground
    subtypes: dict[str, SubtypeBalance]
    staff_per_kt: float = Field(gt=0)  # mining engineers a thousand t a year of capacity
    staff_skills: tuple[str, ...] = Field(min_length=1)  # skills.yaml keys, mean
    grade_noise: float = Field(ge=0)  # log-sd of a month's grade around the profile
    profile_share: float = Field(ge=0)  # x a drill position's log deviation: the grade profile
    energy_share: float = Field(ge=0, le=1)  # of variable cost, x the region's power index
    sustaining_share: float = Field(ge=0)  # sustaining capex a year, x the initial capex
    reclamation_per_t_cents: dict[str, int]  # provisioned a t produced, by subtype
    reclamation_months: int = Field(ge=1)  # paid over this after closure
    strategic: dict[str, float]  # commodity -> strategic weight 0-1
    accident: AccidentBalance
    nationalization: NationalizationBalance
    crash: CrashBalance
    sale: SaleBalance
    rivals: RivalMinersBalance
    transfer_kinds: tuple[str, ...] = Field(min_length=1)  # cost, cost_plus, market

    @model_validator(mode="after")
    def _check(self) -> MiningBalance:
        if set(self.subtypes) != set(SUBTYPES):
            raise ValueError(f"mining.subtypes needs {list(SUBTYPES)}")
        if set(self.reclamation_per_t_cents) != set(SUBTYPES):
            raise ValueError(f"mining.reclamation_per_t_cents needs {list(SUBTYPES)}")
        if any(not 0 <= w <= 1 for w in self.strategic.values()):
            raise ValueError("mining.strategic weights are 0-1")
        if self.capacity_range.lo <= 0:
            raise ValueError("mining.capacity_range starts above 0")
        return self


# --- nationalization_history.yaml (35.4) ------------------------------------------------------


class HistoryEvent(_Frozen):
    """A resource-nationalism event to December 2025 (dossier 5), each cited."""

    month: str  # YYYY-MM
    region: str  # regions.yaml key
    country: str
    commodity: str | None  # geology.yaml commodity key; None: no game commodity (news only)
    kind: Literal["nationalization", "export_ban"]
    months: int = Field(default=0, ge=0)  # an export ban's length (0: a takeover)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)  # dossier 5 tag and row

    @property
    def turn(self) -> int:
        return month_to_turn(self.month)

    @model_validator(mode="after")
    def _check(self) -> HistoryEvent:
        month_to_turn(self.month)
        if self.kind == "export_ban" and self.months <= 0:
            raise ValueError(f"{self.title}: an export ban needs its months")
        return self


class NationalizationHistory(_Frozen):
    last_month: str  # history ends with this month; seeded events after it
    events: tuple[HistoryEvent, ...]

    @property
    def last_turn(self) -> int:
        return month_to_turn(self.last_month)

    @model_validator(mode="after")
    def _check(self) -> NationalizationHistory:
        turns = [e.turn for e in self.events]
        if turns != sorted(turns):
            raise ValueError("nationalization_history.yaml events are in month order")
        if turns and turns[-1] > self.last_turn:
            raise ValueError("an event falls after last_month")
        return self
