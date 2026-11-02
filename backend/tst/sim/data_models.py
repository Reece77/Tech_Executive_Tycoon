"""Pydantic schemas for balance and seed data (ADR-0008).

Model definitions only: this module never reads files. `tst.loader` parses the YAML and
validates it with these models. Unknown keys and out-of-range values fail validation.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.events.data import (
    EFFECT_TYPES,
    LOAN_EFFECTS,
    SEVERITIES,
    TRIGGERS,
    VALUELESS,
    EventTemplate,
)
from tst.sim.money import BP_DENOMINATOR

SCORE_MAX = 100  # quality, feature score, brand and appeal are on 0-100 (formulas.md 11.6)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# ---------------------------------------------------------------------------
# balance.yaml
# ---------------------------------------------------------------------------


class CompanyBalance(_Frozen):
    base_monthly_cost_cents: int = Field(ge=0)


class CostsBalance(_Frozen):
    tools_per_head_cents: int = Field(ge=0)  # M4c: software, equipment and travel per head


class ScenarioBalance(_Frozen):
    starting_cash_cents: int = Field(ge=0)


class DifficultyBalance(_Frozen):
    starting_cash_mult_bp: int = Field(gt=0)


class BackupBalance(_Frozen):
    every_n_turns: int = Field(gt=0)
    keep_periodic: int = Field(gt=0)


class InboxBalance(_Frozen):
    """The inbox (formulas.md 23.1, M10b)."""

    auto_archive_months: int = Field(gt=0)


class HolidayBalance(_Frozen):
    """Auto-advance (formulas.md 17.1)."""

    max_months: int = Field(gt=0)
    default_months: int = Field(gt=0)
    default_stop: Literal["minor", "major", "critical"]
    stop_runway_months: int = Field(ge=0)

    @model_validator(mode="after")
    def _check(self) -> HolidayBalance:
        if self.default_months > self.max_months:
            raise ValueError("holiday.default_months must not exceed holiday.max_months")
        return self


class CooBalance(_Frozen):
    """Ask my COO (formulas.md 17.3)."""

    max_question_chars: int = Field(gt=0)
    max_answer_words: int = Field(gt=0)
    keep_answers: int = Field(gt=0)
    max_issues: int = Field(gt=0)
    runway_months: int = Field(ge=0)
    morale_below: float = Field(ge=0)
    role_open_months: int = Field(ge=0)
    board_below: float = Field(ge=0)


DIFFICULTY_LEVELS = ("easy", "standard", "hard", "ironman")  # ADR-0011
DEFAULT_DIFFICULTY = "standard"
LEVELS = ("junior", "mid", "senior", "staff", "principal", "exec")  # formulas.md section 2


class Span(_Frozen):
    """An inclusive [min, max] pair, written in YAML as a two-item list."""

    lo: float
    hi: float

    @model_validator(mode="before")
    @classmethod
    def _from_list(cls, value: object) -> object:
        if isinstance(value, list | tuple):
            if len(value) != 2:
                raise ValueError("expected [min, max]")
            return {"lo": value[0], "hi": value[-1]}
        return value

    @model_validator(mode="after")
    def _ordered(self) -> Span:
        if self.lo > self.hi:
            raise ValueError(f"min {self.lo} is greater than max {self.hi}")
        return self


class AgeBand(_Frozen):
    from_age: int = Field(ge=0)
    value: float


def _check_bands(bands: tuple[AgeBand, ...], name: str) -> None:
    if not bands or bands[0].from_age != 0:
        raise ValueError(f"{name}: the first band must start at from_age 0")
    ages = [b.from_age for b in bands]
    if ages != sorted(set(ages)):
        raise ValueError(f"{name}: from_age values must be strictly increasing")


def band_value(bands: tuple[AgeBand, ...], age: int) -> float:
    """Value of the last band whose from_age <= age."""
    value = bands[0].value
    for band in bands:
        if age >= band.from_age:
            value = band.value
    return value


class LevelCA(_Frozen):
    mean: float
    sd: float = Field(ge=0)


class SkillNoise(_Frozen):
    primary: float = Field(ge=0)
    secondary: float = Field(ge=0)


class PeopleBalance(_Frozen):
    level_ca: dict[str, LevelCA]
    level_age: dict[str, Span]
    ca_clip: Span
    skill_noise_sd: SkillNoise
    secondary_offset: float
    other_skill_range: Span
    ca_tolerance: float = Field(gt=0)
    pa_gap_mean: tuple[AgeBand, ...]
    pa_gap_sd: float = Field(ge=0)
    personality_mean: float
    personality_sd: float = Field(ge=0)
    interest_count: Span
    max_tags: int = Field(ge=0)
    region_weights: dict[str, float]
    retire_bp_per_year_over_60: int = Field(ge=0)
    retire_from_age: int = Field(gt=0)

    @model_validator(mode="after")
    def _check(self) -> PeopleBalance:
        for name, table in (("level_ca", self.level_ca), ("level_age", self.level_age)):
            if sorted(table) != sorted(LEVELS):
                raise ValueError(f"{name} must define exactly {list(LEVELS)}")
        _check_bands(self.pa_gap_mean, "pa_gap_mean")
        if any(w < 0 for w in self.region_weights.values()) or not any(
            w > 0 for w in self.region_weights.values()
        ):
            raise ValueError("region_weights must be non-negative with at least one positive")
        return self


class PayrollBalance(_Frozen):
    salary_round_to_cents: int = Field(gt=0)
    benefits_bp: int = Field(ge=0)
    office_cost_per_head_cents: int = Field(ge=0)
    severance_months: int = Field(ge=0)


class GrowthBalance(_Frozen):
    rate: float = Field(ge=0)
    age_factor: tuple[AgeBand, ...]
    decline: tuple[AgeBand, ...]
    noise_rel_sd: float = Field(ge=0)

    @model_validator(mode="after")
    def _check(self) -> GrowthBalance:
        _check_bands(self.age_factor, "age_factor")
        _check_bands(self.decline, "decline")
        return self


REVEAL_ACTIONS = (
    "job_post_screen",
    "network_intro",
    "interview",
    "reference_check",
    "scouting_month",
    "employed_month",
)


class InitialHalfWidth(_Frozen):
    skill: float = Field(ge=0)
    personality: float = Field(ge=0)
    pa: float = Field(ge=0)


class RevealBalance(_Frozen):
    initial_hw: InitialHalfWidth
    strength: dict[str, float]
    scout_base: float
    scout_divisor: float = Field(gt=0)
    pa_scout_divisor: float = Field(gt=0)
    founder_pa_hw: float = Field(ge=0)
    pa_scout_clamp: Span
    pa_strength: dict[str, float]
    pa_phrase_bounds: tuple[float, ...]

    @model_validator(mode="after")
    def _check(self) -> RevealBalance:
        for name, table in (("strength", self.strength), ("pa_strength", self.pa_strength)):
            if sorted(table) != sorted(REVEAL_ACTIONS):
                raise ValueError(f"{name} must define exactly {list(REVEAL_ACTIONS)}")
            if any(not 0 <= s <= 1 for s in table.values()):
                raise ValueError(f"{name} values must be fractions in [0, 1]")
        if list(self.pa_phrase_bounds) != sorted(self.pa_phrase_bounds):
            raise ValueError("pa_phrase_bounds must be increasing")
        return self


class FounderBalance(_Frozen):
    skill_base: float
    skill_points: int = Field(ge=0)
    skill_cap: float
    default_age: int
    age_range: Span
    default_region: str
    energy_per_month: int = Field(ge=0)
    energy_cost: dict[str, int]

    @model_validator(mode="after")
    def _check(self) -> FounderBalance:
        if not self.age_range.lo <= self.default_age <= self.age_range.hi:
            raise ValueError("default_age must be within age_range")
        if self.skill_base > self.skill_cap:
            raise ValueError("skill_base must not exceed skill_cap")
        if sorted(self.energy_cost) != sorted(ENERGY_ACTIONS):
            raise ValueError(f"energy_cost must define exactly {list(ENERGY_ACTIONS)}")
        return self


ENERGY_ACTIONS = (
    "interview",
    "reference_check",
    "job_post",
    "recruiter",
    "network",
    "offer",
    # M2 org actions (formulas.md section 6)
    "create_unit",
    "dissolve_unit",
    "move_unit",
    "set_leader",
    "move_person",
    "set_policy",
    "give_raise",
    "promote",
    "hiring_plan",
    # M3 product actions and founder scouting (formulas.md sections 6, 11)
    "scout_search",
    "create_product",
    "assign_unit",
    "unassign_unit",
    "set_price",
    "set_marketing",
    "add_segment",
    "launch_product",
    "sunset_product",
    "cancel_product",
    # M4 finance (formulas.md sections 6, 14)
    "raise_safe",
    "start_round",
    "accept_term_sheet",
    "accept_bridge",
    "name_nominee",
    # M5 rivals (formulas.md 15.6)
    "poach_search",
    "choose_event",  # M6 (formulas.md 16.3): energy 0
    "appoint_executive",  # M8 (formulas.md 18.3)
    "remove_executive",  # M8 (18.3)
    "set_product_division",  # M8 (18.1)
    "set_shared_services",  # M8 (18.4)
)
CHANNELS = ("network", "job_post", "recruiter")  # formulas.md section 7
HIRING_LEVELS = ("junior", "mid", "senior", "staff")


class ChannelBalance(_Frozen):
    size: Span
    sociability_bonus: int = Field(ge=0)
    sociability_threshold: float = Field(ge=0)
    level_mix: dict[str, float]
    knowledge: tuple[str, ...]

    @model_validator(mode="after")
    def _check(self) -> ChannelBalance:
        unknown = sorted(set(self.level_mix) - set(LEVELS))
        if unknown:
            raise ValueError(f"level_mix has unknown levels {unknown}")
        if any(w < 0 for w in self.level_mix.values()) or not any(
            w > 0 for w in self.level_mix.values()
        ):
            raise ValueError("level_mix needs non-negative weights with one positive")
        bad = sorted(set(self.knowledge) - set(REVEAL_ACTIONS))
        if bad:
            raise ValueError(f"knowledge has unknown actions {bad}")
        return self


class OfferBalance(_Frozen):
    w_salary: float
    w_equity: float
    w_fit: float
    w_risk: float
    ambition_equity_boost: float
    ambition_boost_above: float
    equity_value_per_bp: float
    stage_appeal: dict[int, float]
    stage_equity_mult: dict[int, float]
    k: float
    threshold: float


class HiringBalance(_Frozen):
    hint_bands: Span
    channel: dict[str, ChannelBalance]
    job_post_cost_cents: int = Field(ge=0)
    recruiter_fee_bp: int = Field(ge=0)
    candidate_shelf_turns: int = Field(gt=0)
    lowball_ratio: float = Field(ge=0)
    max_offer_equity_bp: int = Field(ge=0)
    relocation_cents: int = Field(default=0, ge=0)  # M9 (19.3): a relocating hire's fee
    pitch_per_recruiting: float
    pitch_neutral: float
    offer: OfferBalance

    @model_validator(mode="after")
    def _check(self) -> HiringBalance:
        if sorted(self.channel) != sorted(CHANNELS):
            raise ValueError(f"channel must define exactly {list(CHANNELS)}")
        return self


class MoraleBalance(_Frozen):
    new_hire: float
    target_base: float
    pay_slope: float
    pay_min: float
    pay_max: float
    fit_per_interest: float
    work_style_mismatch: float
    runway_warn_months: float
    runway_crit_months: float
    runway_warn: float
    runway_crit: float
    workload_term: float
    rate: float = Field(ge=0, le=1)
    noise_scale: float = Field(ge=0)
    fire_penalty: float
    fire_penalty_culture_carrier: float


class ResignBalance(_Frozen):
    base_bp: float = Field(ge=0)
    cap_bp: float = Field(ge=0)
    morale_floor: float
    morale_divisor: float = Field(gt=0)
    loyalty_divisor: float = Field(gt=0)
    job_hopper_mult: float = Field(ge=0)


class TagsBalance(_Frozen):
    reveal_bp_per_month: int = Field(ge=0)
    reveal_bp_on_check: int = Field(ge=0)


# Teammate tags with a morale term (formulas.md 13.6). From M6 credit_taker and
# toxic_high_performer act through relationships instead (16.7).
ORG_TAGS = ("culture_carrier",)
MENTOR_TAG = "mentor"  # formulas.md 13.5


class ReorgBalance(_Frozen):
    move: float
    new_leader_members: float
    replaced_leader: float
    dissolve_members: float


class RemoteBalance(_Frozen):
    sociable_at: float
    sociable_morale: float
    solitary_at: float
    solitary_morale: float


class OrgBalance(_Frozen):
    department_unlock_headcount: int = Field(ge=0)
    span_base: int = Field(ge=1)
    span_per_leadership: float = Field(gt=0)
    manager_morale_slope: float
    manager_morale_cap: float = Field(ge=0)
    manager_label_bands: Span
    mentoring_neutral: float
    mentoring_divisor: float = Field(gt=0)
    mentor_tag_bonus: float
    growth_mult_min: float = Field(ge=0)
    growth_mult_max: float = Field(ge=0)
    tag_morale: dict[str, float]
    tag_morale_cap: dict[str, float]
    reorg: ReorgBalance
    raise_morale: float
    raise_threshold_bp: int = Field(ge=0)
    raise_cooldown_turns: int = Field(ge=0)
    pay_cut_morale: float
    promote_morale: float
    remote: RemoteBalance
    # M8 (formulas.md 18.1-18.4): divisions, coordination cost and support
    division_stage: int = Field(ge=0)
    max_divisions: int = Field(ge=0)
    layer_tax: float = Field(ge=0)
    layer_floor: float = Field(ge=0, le=1)
    layer_free_depth: int = Field(ge=0)
    cross_division_factor: float = Field(gt=0, le=1)
    support_ratio: float = Field(gt=0)
    support_shortfall: float = Field(ge=0, le=1)
    support_morale: float
    embedded_bonus: float = Field(gt=0)
    support_churn: float = Field(ge=0)  # churn x (1 + support_churn (1 - c) k_COO) (18.4)

    @model_validator(mode="after")
    def _check(self) -> OrgBalance:
        if self.growth_mult_min > self.growth_mult_max:
            raise ValueError("growth_mult_min must not exceed growth_mult_max")
        for name, table in (
            ("tag_morale", self.tag_morale),
            ("tag_morale_cap", self.tag_morale_cap),
        ):
            if sorted(table) != sorted(ORG_TAGS):
                raise ValueError(f"{name} must define exactly {list(ORG_TAGS)}")
        for tag in ORG_TAGS:
            effect, cap = self.tag_morale[tag], self.tag_morale_cap[tag]
            if effect * cap < 0:
                raise ValueError(
                    f"tag_morale_cap.{tag} must have the same sign as tag_morale.{tag}"
                )
        return self


class SeatDef(_Frozen):
    """One executive seat (formulas.md 18.3): skill weights of the seat score s and the
    coefficient of its effect."""

    label: str = Field(min_length=1)
    weights: dict[str, float]
    effect: float = Field(ge=0)
    confidence: float = Field(default=0.0, ge=0)  # CFO: director confidence a month per e
    # M8 redesign (Reece, 2026-10-31): effects that still matter at a plateau (18.3)
    qcap: float = Field(default=0.0, ge=0)  # CTO: Q_cap x (1 + qcap e)
    churn: float = Field(default=0.0, ge=0)  # CPO: base churn x (1 - churn e)
    brand: float = Field(default=0.0, ge=0)  # CMO: B* x (1 + brand e), at most 100
    awareness: float = Field(default=0.0, ge=0)  # CMO: awareness x (1 + awareness e)
    pricing: float = Field(default=0.0, ge=0)  # CRO: p_ref x (1 + pricing e) in sales segments

    @model_validator(mode="after")
    def _check(self) -> SeatDef:
        if any(w < 0 for w in self.weights.values()) or not _sums_to_one(self.weights.values()):
            raise ValueError("exec seat weights must be >= 0 and sum to 1")
        return self


class ExecSeatsBalance(_Frozen):
    stage: int = Field(ge=0)
    min_level: str
    score_mid: float
    score_span: float = Field(gt=0)
    effect_min: float
    effect_max: float
    vacant_effect: float
    appoint_morale: float
    remove_morale: float
    fit_bands: Span  # displayed seat score: below lo "weak", from hi "strong", else "fair"
    seats: dict[str, SeatDef] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> ExecSeatsBalance:
        if self.min_level not in LEVELS:
            raise ValueError(f"exec_seats.min_level must be one of {list(LEVELS)}")
        if self.effect_min > self.effect_max:
            raise ValueError("exec_seats.effect_min exceeds effect_max")
        return self


class DelegatesBalance(_Frozen):
    energy_per_month: int = Field(ge=0)
    scout_cost: int = Field(ge=0)
    max_ratio_bp: int = Field(gt=0)


# --- Products and markets (M3, formulas.md section 11) -------------------------------------

PRODUCT_TAGS = ("quiet_genius", "toxic_high_performer", "perfectionist", "maverick")  # 11.10


class TagOutput(_Frozen):
    output: float = Field(gt=0)


class ProductsBalance(_Frozen):
    start_quality: float = Field(ge=0, le=100)
    launch_min_quality: float = Field(ge=0, le=100)
    launch_min_feature: float = Field(ge=0, le=100)
    morale_factor_base: float = Field(ge=0)
    morale_factor_slope: float
    coord_free_builders: int = Field(ge=0)
    coord_per_builder: float = Field(ge=0)
    coord_floor: float = Field(ge=0, le=1)
    dev_noise_sd: float = Field(ge=0)
    maverick_noise_sd: float = Field(ge=0)
    dev_noise_sd_cap: float = Field(ge=0)
    seller_rate: dict[str, float]
    marketer_mk: float = Field(ge=0)
    budget_mk_unit_cents: int = Field(gt=0)
    qcap_per_skill: float = Field(gt=0)
    quality_rate: float = Field(ge=0, le=1)
    overcap_decay: float = Field(ge=0, le=1)
    rot_threshold: float = Field(ge=0)
    rot_per_month: float = Field(ge=0)
    brand_rate: float = Field(ge=0, le=1)
    tag: dict[str, TagOutput]
    perfectionist_qcap_bonus: float = Field(ge=0)
    pace_bands: Span
    arr_milestones_cents: tuple[int, ...]
    growth_label_months: int = Field(gt=0)
    growth_label_rate: float

    @model_validator(mode="after")
    def _check(self) -> ProductsBalance:
        if sorted(self.tag) != sorted(PRODUCT_TAGS):
            raise ValueError(f"tag must define exactly {list(PRODUCT_TAGS)}")
        if any(r < 0 for r in self.seller_rate.values()):
            raise ValueError("seller_rate values must be non-negative")
        milestones = list(self.arr_milestones_cents)
        if milestones != sorted(set(milestones)) or any(m <= 0 for m in milestones):
            raise ValueError("arr_milestones_cents must be positive and strictly increasing")
        return self


class MarketBalance(_Frozen):
    gamma: float = Field(gt=0)
    awareness_floor: float = Field(ge=0)
    awareness_scale: float = Field(ge=0, le=1)
    demand_noise_sd: float = Field(ge=0)
    gap_divisor: float = Field(gt=0)
    low_quality_at: float = Field(ge=0, le=100)
    low_quality_churn_mult: float = Field(ge=0)
    sunset_churn_mult: float = Field(ge=0)


SERIES = ("seed", "a", "b", "c", "d")  # priced rounds, in order (14.5; c and d M10, 20.2)
type Series = Literal["seed", "a", "b", "c", "d"]


class StagesBalance(_Frozen):
    arr_cents: dict[int, int]
    funding: dict[int, Series] = Field(default_factory=dict)  # M4: a closed round's stage (14.8)

    @model_validator(mode="after")
    def _check(self) -> StagesBalance:
        ordered = [self.arr_cents[k] for k in sorted(self.arr_cents)]
        if ordered != sorted(ordered) or any(v <= 0 for v in ordered):
            raise ValueError("arr_cents must be positive and rise with the stage")
        return self


class FloorCents(_Frozen):
    no_product: int = Field(gt=0)
    live: int = Field(gt=0)


class SafeBalance(_Frozen):
    min_cents: int = Field(gt=0)
    max_cents: int = Field(gt=0)
    optimism: float = Field(gt=0)
    steepness: float = Field(gt=0)
    fee_cents: int = Field(ge=0)
    hint_bands: Span
    max_fraction: float = Field(gt=0, lt=1)

    @model_validator(mode="after")
    def _check(self) -> SafeBalance:
        if self.min_cents > self.max_cents:
            raise ValueError("safe.min_cents must not exceed safe.max_cents")
        return self


class RoundBalance(_Frozen):
    open_turns: int = Field(gt=0)
    valuation_noise_sd: float = Field(ge=0)
    max_amount_of_pre: float = Field(gt=0, le=1)
    max_response: float = Field(gt=0, le=1)
    gate_arr_cents: dict[Series, int]
    fee_min_cents: int = Field(ge=0)
    fee_bp: int = Field(ge=0, le=BP_DENOMINATOR)
    typical_cents: dict[Series, Span]  # guidance only (14.5 table)
    heat_max: float = Field(ge=1)  # M4c: most a Series A or B's ARR / gate multiplies response
    heat_seed_live: float = Field(ge=1)  # M4c: a seed's heat with a live product


class FinanceBalance(_Frozen):
    initial_fd_shares: int = Field(gt=0)
    pool_target_bp: int = Field(ge=0, lt=BP_DENOMINATOR)
    vesting_months: int = Field(gt=0)
    cliff_months: int = Field(ge=0)
    retention_slope: float = Field(ge=0)
    retention_floor: float = Field(ge=0, le=1)
    growth_window_months: int = Field(gt=0)
    new_revenue_growth: float = Field(ge=0)
    multiple_base: float = Field(ge=0)
    multiple_per_growth: float = Field(ge=0)
    multiple_min: float = Field(ge=0)
    multiple_max: float = Field(gt=0)
    floor_cents: FloorCents
    floor_per_head_cents: int = Field(ge=0)
    floor_head_cap: int = Field(ge=0)
    safe: SafeBalance
    round: RoundBalance

    @model_validator(mode="after")
    def _check(self) -> FinanceBalance:
        if self.cliff_months > self.vesting_months:
            raise ValueError("cliff_months must not exceed vesting_months")
        if self.multiple_min > self.multiple_max:
            raise ValueError("multiple_min must not exceed multiple_max")
        return self


class RunwayTerm(_Frozen):
    min_months: float = Field(ge=0)
    points: float


class SeatCounts(_Frozen):
    common: int = Field(ge=1)
    investor: int = Field(ge=0)
    independent: int = Field(ge=0)


class BoardBalance(_Frozen):
    start: float = Field(ge=0, le=SCORE_MAX)
    rate: float = Field(gt=0, le=1)
    target_base: float
    growth_weight: float = Field(ge=0)
    expected_growth: dict[Series, float]
    runway_terms: tuple[RunwayTerm, ...] = Field(min_length=1)
    no_product_penalty: float
    no_product_after_turns: int = Field(ge=0)
    down_round_hit: float
    warning_below: float = Field(ge=0, le=SCORE_MAX)
    removal_below: float = Field(ge=0, le=SCORE_MAX)
    removal_months: int = Field(gt=0)
    meeting_months: tuple[int, ...]
    history_months: int = Field(gt=0)
    trend_points: float = Field(ge=0)
    seats: dict[Series, SeatCounts]
    max_seats: int = Field(ge=1)  # M10 (20.2): the most seats a board has, the founder's included
    director_role: str
    director_level: str

    @model_validator(mode="after")
    def _check(self) -> BoardBalance:
        mins = [t.min_months for t in self.runway_terms]
        if mins != sorted(mins, reverse=True) or mins[-1] != 0:
            raise ValueError("runway_terms must run from the most months down to 0")
        if any(not 1 <= m <= MONTHS_PER_YEAR for m in self.meeting_months):
            raise ValueError("meeting_months must be calendar months 1..12")
        if sorted(self.expected_growth) != sorted(SERIES) or sorted(self.seats) != sorted(SERIES):
            raise ValueError(f"expected_growth and seats must cover {list(SERIES)}")
        if self.director_level not in LEVELS:
            raise ValueError(f"director_level must be one of {list(LEVELS)}")
        if any(c.common + c.investor + c.independent > self.max_seats for c in self.seats.values()):
            raise ValueError(f"no series may seat more than max_seats ({self.max_seats})")
        return self


class BankruptcyBalance(_Frozen):
    months: int = Field(gt=0)
    bridge_burn_months: float = Field(gt=0)
    bridge_cap_of_post: float = Field(gt=0)
    bridge_min_confidence: float = Field(ge=0, le=SCORE_MAX)
    bridge_open_turns: int = Field(gt=0)


# --- Rivals (formulas.md section 15, M5) -----------------------------------------------------

PERSONALITIES = ("aggressive", "fast_follower", "premium", "cost_leader")  # 15.3 (acquirer: v2)
RIVAL_ACTIONS = (
    "price_cut",
    "price_rise",
    "feature_push",
    "quality_push",
    "brand_push",
    "enter_segment",
    "cut_costs",
    "poach",
)  # formulas.md 15.3, in scoring order (ties go to the earlier action)
FUNCTIONS = ("builder", "seller", "marketer")  # 15.1 workforce pool functions


class RivalNeedBalance(_Frozen):
    price_cut_drop: float = Field(gt=0)
    price_rise_lead: float
    price_rise_span: float = Field(gt=0)
    feature_gap: float = Field(gt=0)
    quality_gap: float = Field(gt=0)
    brand_gap: float = Field(gt=0)
    enter_unserved: float = Field(ge=0, le=1)
    enter_span: float = Field(gt=0)
    enter_cash_months: float = Field(ge=0)
    cut_costs_months: float = Field(ge=0)
    cut_costs_span: float = Field(gt=0)
    poach_gain: float = Field(gt=0)


class StartupBalance(_Frozen):
    found_rate: float = Field(ge=0, le=1)
    max_alive: int = Field(ge=0)
    team: Span
    cash_cents: Span
    raise_months: float = Field(gt=0)
    raise_chance: float = Field(ge=0, le=1)
    low_cash_months: float = Field(ge=0)
    salary_mult: float = Field(gt=0)
    personalities: tuple[str, ...] = Field(min_length=1)


class PoachBalance(_Frozen):
    offer_mult: float = Field(gt=0)
    top_fraction: float = Field(gt=0, le=1)
    seat_holder_weight: float = Field(ge=0)  # M10d: a seat holder's weight in the target draw
    ask_mult: float = Field(gt=0)
    leave_penalty: float
    key_builder_quality_hit: float = Field(ge=0)
    bands: Span
    candidates: Span
    salary_weight: float
    morale_mid: float
    morale_divisor: float = Field(gt=0)
    loyalty_mid: float
    loyalty_divisor: float = Field(gt=0)
    options_weight: float
    steepness: float = Field(gt=0)


class RivalsBalance(_Frozen):
    act_threshold: float
    noise_sd: float = Field(ge=0)
    cooldown_turns: int = Field(ge=0)
    push_turns: int = Field(gt=0)
    window_turns: int = Field(gt=0)
    need: RivalNeedBalance
    weights: dict[str, dict[str, float]]
    price_factor: dict[str, float]
    price_cut: float = Field(gt=0)
    price_rise: float = Field(gt=0)
    push_pool_growth: float = Field(ge=0)
    brand_push_marketing: float = Field(ge=0)
    cut_costs_pools: float = Field(ge=0, lt=1)
    cut_costs_marketing: float = Field(ge=0, le=1)
    feature_push_rate: float = Field(ge=0)
    quality_push_rate: float = Field(ge=0)
    brand_push_rate: float = Field(ge=0)
    cut_costs_drag: float = Field(ge=0)
    qcap_per_skill: float = Field(gt=0)
    function_mix: dict[str, dict[str, float]]
    function_roles: dict[str, str]
    pool_morale: float = Field(ge=0, le=100)  # tunable-exempt: morale scale 0-100
    pool_skill_other: float = Field(ge=1, le=20)  # tunable-exempt: attribute scale 1-20
    start_marketing_share: float = Field(ge=0, le=1)
    key_people: int = Field(ge=0)
    key_people_levels: dict[str, float]
    free_agent_months: int = Field(ge=0)
    startup: StartupBalance
    poach: PoachBalance
    money_bands_months: Span
    stance_turns: int = Field(ge=0)
    headcount_round: int = Field(gt=0)
    headcount_round_above: int = Field(ge=0)

    @model_validator(mode="after")
    def _check(self) -> RivalsBalance:
        for name, table in (("weights", self.weights), ("price_factor", self.price_factor)):
            if sorted(table) != sorted(PERSONALITIES):
                raise ValueError(f"rivals.{name} must define exactly {list(PERSONALITIES)}")
        for personality, weights in self.weights.items():
            if sorted(weights) != sorted(RIVAL_ACTIONS):
                raise ValueError(f"rivals.weights.{personality} must define {list(RIVAL_ACTIONS)}")
        for category, mix in self.function_mix.items():
            if sorted(mix) != sorted(FUNCTIONS) or abs(sum(mix.values()) - 1) > WEIGHT_TOLERANCE:
                raise ValueError(f"rivals.function_mix.{category} must split 1 over {FUNCTIONS}")
        if sorted(self.function_roles) != sorted(FUNCTIONS):
            raise ValueError(f"rivals.function_roles must define exactly {list(FUNCTIONS)}")
        unknown = sorted(set(self.key_people_levels) - set(LEVELS))
        if unknown:
            raise ValueError(f"rivals.key_people_levels has unknown levels {unknown}")
        bad = sorted(set(self.startup.personalities) - set(PERSONALITIES))
        if bad:
            raise ValueError(f"rivals.startup.personalities has unknown personalities {bad}")
        return self


class TriggerBalance(_Frozen):
    """One trigger's thresholds (formulas.md 16.2); unused fields stay None."""

    below: float | None = None
    span: float | None = Field(default=None, gt=0)
    at_most: float | None = None
    at_least: float | None = None
    strength: float | list[float] | None = None
    top_fraction: float | None = Field(default=None, gt=0, le=1)
    tenure_months: int | None = Field(default=None, ge=0)
    unit_size: int | None = Field(default=None, ge=2)
    months: list[float] | None = None


class CrisisBalance(_Frozen):
    """Critical events from crises (formulas.md 23.3, M10b)."""

    key_exit_top_fraction: float = Field(gt=0, le=1)
    breach_chance: float = Field(ge=0, le=1)
    breach_min_customers: float = Field(ge=0)
    security_full_at: float = Field(gt=0)
    outage_chance: float = Field(ge=0, le=1)
    outage_max_quality: float = Field(ge=0)
    outage_min_customers: float = Field(ge=0)


AUTHORITY_SEATS = ("cto", "cro", "cmo", "coo", "cfo")  # seats that take authority (24.1)


class ExecQuality(_Frozen):
    base: float = Field(ge=0, le=1)
    per_score: float = Field(ge=0)
    min: float = Field(ge=0, le=1)
    max: float = Field(ge=0, le=1)


class ExecAuthorityBalance(_Frozen):
    """Executives with authority (formulas.md 24, M10c)."""

    change_energy: int = Field(ge=0)
    energy_per_month: int = Field(gt=0)
    quality: ExecQuality
    mistake_budget_off: float = Field(ge=0, le=1)
    report_months: int = Field(gt=0)
    plan_hires: int = Field(gt=0)
    memory_months: int = Field(gt=0)
    move_margin: float = Field(ge=1)
    price_step_pct: float = Field(ge=0)
    lease_seats: int = Field(gt=0)
    repay_share: float = Field(ge=0, le=1)
    loan_share: float = Field(gt=0, le=1)
    defaults: dict[str, dict[str, Any]]

    @model_validator(mode="after")
    def _check(self) -> ExecAuthorityBalance:
        if sorted(self.defaults) != sorted(AUTHORITY_SEATS):
            raise ValueError(f"exec_authority.defaults must cover {list(AUTHORITY_SEATS)}")
        return self


class EventsBalance(_Frozen):
    """Event director, effect caps and storylines (formulas.md 16)."""

    count_weights: list[float]
    category_repeat_factor: float = Field(ge=0)
    template_cooldown_turns: int = Field(ge=0)
    person_cooldown_turns: int = Field(ge=0)
    critical_gap_turns: int = Field(ge=0)
    major_from: float = Field(ge=0, le=1)
    light_tone_chance_bp: int = Field(ge=0, le=10_000)  # tunable-exempt: basis-point scale
    max_storylines: int = Field(ge=0)
    summary_words: int = Field(gt=0)
    body_words: int = Field(gt=0)
    recent_summaries: int = Field(ge=0)
    trigger: dict[str, TriggerBalance]
    caps: dict[str, list[float]]
    cash_revenue_months: float = Field(ge=0)
    cash_gain_share: float = Field(ge=0, le=1)
    effect_size_bounds: Span
    modifier_months: list[int]  # M10b (23.2): the longest a modifier runs, by severity
    crisis: CrisisBalance  # M10b (23.3)

    @model_validator(mode="after")
    def _check(self) -> EventsBalance:
        counts, tolerance = 4, 1e-9  # tunable-exempt: 0-3 events (16.1), float tolerance
        if len(self.count_weights) != counts or abs(sum(self.count_weights) - 1) > tolerance:
            raise ValueError("events.count_weights: four probabilities (0-3 events) summing to 1")
        if sorted(self.trigger) != sorted(TRIGGERS):
            raise ValueError(f"events.trigger must cover exactly {list(TRIGGERS)}")
        # M10: loan effects are shares of debt.breach's sizes, not capped here (20.3).
        sized = sorted(set(EFFECT_TYPES) - set(VALUELESS) - {"resign"} - set(LOAN_EFFECTS))
        if sorted(self.caps) != sized:
            raise ValueError(f"events.caps must cover exactly {sized}")
        for effect, caps in self.caps.items():
            if len(caps) != len(SEVERITIES) or any(c <= 0 for c in caps) or caps != sorted(caps):
                raise ValueError(f"events.caps.{effect}: three rising positive caps")
        months = self.modifier_months
        if len(months) != len(SEVERITIES) or any(m < 1 for m in months) or months != sorted(months):
            raise ValueError("events.modifier_months: three rising positive month counts")
        return self

    def cap(self, effect: str, severity: str) -> float:
        return self.caps[effect][SEVERITIES.index(severity)]

    def max_months(self, severity: str) -> int:
        """The longest a modifier of this severity runs (23.2)."""
        return self.modifier_months[SEVERITIES.index(severity)]


class RelationshipsBalance(_Frozen):
    """Relationships between unit-mates and manager links (formulas.md 16.7)."""

    start_base: float
    start_per_temperament: float = Field(ge=0)
    start_clamp: Span
    drift: float = Field(ge=0, le=1)
    tag_push: dict[str, float]
    politician_ambition_at: float = Field(ge=1, le=20)  # tunable-exempt: attribute scale 1-20
    morale_weight: float = Field(ge=0)
    morale_cap: float = Field(ge=0)
    label_bounds: list[float]
    range: Span

    @model_validator(mode="after")
    def _check(self) -> RelationshipsBalance:
        labels = 5  # tunable-exempt: hostile, strained, neutral, good, close (16.7)
        if len(self.label_bounds) != labels - 1 or self.label_bounds != sorted(self.label_bounds):
            raise ValueError("relationships.label_bounds: four rising bounds")
        return self


# --- Capital and macro (formulas.md section 20, M10) -----------------------------------------


class Ar1Balance(_Frozen):
    """x' = mean + phi (x - mean) + N(0, shock_sd), clamped to bounds (20.1)."""

    mean: float
    phi: float = Field(ge=0, le=1)
    shock_sd: float = Field(ge=0)
    bounds: Span

    @model_validator(mode="after")
    def _check(self) -> Ar1Balance:
        if not self.bounds.lo <= self.mean <= self.bounds.hi:
            raise ValueError("an AR(1) mean must lie inside its bounds")
        return self


class DownturnBalance(_Frozen):
    monthly: float = Field(ge=0, le=1)
    gap_months: int = Field(ge=0)
    months: int = Field(gt=0)
    rate: float
    climate: float
    confidence: float


class MacroBalance(_Frozen):
    history_months: int = Field(gt=0)
    rate: Ar1Balance
    climate: Ar1Balance
    confidence: Ar1Balance
    ai_change: Ar1Balance
    confidence_exponent: float = Field(ge=0)
    confidence_segments: tuple[str, ...]
    downturn: DownturnBalance


class VentureDebtBalance(_Frozen):
    window_turns: int = Field(gt=0)
    max_of_round_bp: int = Field(gt=0, le=BP_DENOMINATOR)
    spread_bp: int = Field(ge=0)
    term_months: int = Field(gt=0)
    interest_only_months: int = Field(ge=0)
    warrant_bp: int = Field(ge=0, lt=BP_DENOMINATOR)
    covenant_burn_months: float = Field(ge=0)

    @model_validator(mode="after")
    def _check(self) -> VentureDebtBalance:
        if self.interest_only_months >= self.term_months:
            raise ValueError("interest_only_months must be shorter than term_months")
        return self


class BankLoanBalance(_Frozen):
    stage: int = Field(ge=0)
    profit_months: int = Field(gt=0)
    max_of_arr_bp: int = Field(gt=0)
    spread_bp: int = Field(ge=0)
    term_months: int = Field(gt=0)
    covenant_profit_months: int = Field(gt=0)
    covenant_cash_bp: int = Field(ge=0)


class BreachBalance(_Frozen):
    waiver_fee_bp: int = Field(ge=0, le=BP_DENOMINATOR)
    rate_up_bp: int = Field(ge=0)
    repay_bp: int = Field(ge=0, le=BP_DENOMINATOR)
    cure_months: int = Field(ge=0)
    call_window_months: int = Field(ge=0)


class DebtBalance(_Frozen):
    take_energy: int = Field(ge=0)
    repay_energy: int = Field(ge=0)
    venture: VentureDebtBalance
    bank: BankLoanBalance
    min_cents: int = Field(gt=0)
    breach: BreachBalance


class OfficeBalance(_Frozen):
    """Offices (formulas.md 19.2, M9)."""

    seat_sizes: tuple[int, ...] = Field(min_length=1)
    lease_discount: float = Field(gt=0)
    fit_out_months: int = Field(ge=0)
    close_penalty_months: int = Field(ge=0)
    crowded_morale: float
    lease_energy: int = Field(ge=0)
    close_energy: int = Field(ge=0)
    assign_energy: int = Field(ge=0)


class RegionalMarketsBalance(_Frozen):
    """Regional markets (formulas.md 19.4-19.5, M9)."""

    localize_cents: int = Field(ge=0)
    localize_scope: float = Field(gt=0)
    localize_months: int = Field(ge=0)
    localize_slowdown: float = Field(ge=0, le=1)
    launch_energy: int = Field(ge=0)
    foreign_awareness: float = Field(ge=0, le=1)
    no_marketing_awareness: float = Field(ge=0, le=1)  # M10b (23.5)
    presence_people: int = Field(ge=0)
    neighbour_sellers: float = Field(ge=0, le=1)
    cross_region_step: float = Field(ge=0)
    cross_region_floor: float = Field(ge=0, le=1)


class RegionEntryBalance(_Frozen):
    unserved: float = Field(ge=0, le=1)
    span: float = Field(gt=0)
    cash_months: float = Field(ge=0)
    cooldown_turns: int = Field(ge=0)


class GeoBalance(_Frozen):
    """Cities and geography (formulas.md 19.1, 19.3, 19.6, M9)."""

    default_hq_city: str
    pay_level: float = Field(gt=0)
    local_candidates: float = Field(ge=0, le=1)
    region_entry: RegionEntryBalance


class Balance(_Frozen):
    company: CompanyBalance
    costs: CostsBalance  # M4c (formulas.md 8)
    scenario: dict[str, ScenarioBalance]
    difficulty: dict[str, DifficultyBalance]
    backup: BackupBalance
    holiday: HolidayBalance  # M7b (formulas.md 17.1)
    exec_authority: ExecAuthorityBalance  # M10c (formulas.md 24)
    inbox: InboxBalance  # M10b (formulas.md 23.1)
    coo: CooBalance  # M7b (formulas.md 17.3)
    people: PeopleBalance
    payroll: PayrollBalance
    growth: GrowthBalance
    reveal: RevealBalance
    founder: FounderBalance
    hiring: HiringBalance
    morale: MoraleBalance
    resign: ResignBalance
    tags: TagsBalance
    org: OrgBalance
    delegates: DelegatesBalance
    products: ProductsBalance
    market: MarketBalance
    stages: StagesBalance
    finance: FinanceBalance
    board: BoardBalance
    bankruptcy: BankruptcyBalance
    rivals: RivalsBalance  # M5 (formulas.md 15)
    events: EventsBalance  # M6 (formulas.md 16)
    relationships: RelationshipsBalance  # M6 (formulas.md 16.7)
    exec_seats: ExecSeatsBalance  # M8 (formulas.md 18.3)
    macro: MacroBalance  # M10 (formulas.md 20.1)
    debt: DebtBalance  # M10 (formulas.md 20.3)
    office: OfficeBalance  # M9 (formulas.md 19.2)
    markets: RegionalMarketsBalance  # M9 (formulas.md 19.4-19.5)
    geo: GeoBalance  # M9 (formulas.md 19.1, 19.3, 19.6)

    @model_validator(mode="after")
    def _check_difficulties(self) -> Balance:
        if sorted(self.difficulty) != sorted(DIFFICULTY_LEVELS):
            raise ValueError(
                f"difficulty must define exactly {list(DIFFICULTY_LEVELS)}, "
                f"got {sorted(self.difficulty)}"
            )
        return self


# ---------------------------------------------------------------------------
# Seed data files
# ---------------------------------------------------------------------------

type AccountType = Literal["asset", "liability", "equity", "revenue", "expense"]


class Account(_Frozen):
    code: str = Field(pattern=r"^\d{4}_[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    type: AccountType


class CapTableGroup(_Frozen):
    name: str = Field(min_length=1, max_length=80)  # tunable-exempt: holder name column width
    shares: int = Field(gt=0)


class ScenarioSeed(_Frozen):
    lead: str  # investors.yaml firm key
    amount_cents: int = Field(gt=0)
    shares: int = Field(gt=0)


class ScenarioCapTable(_Frozen):
    """Shares at game start (formulas.md 14.2); the total is checked against FD at load."""

    founder: int = Field(gt=0)
    pool: int = Field(ge=0)
    others: tuple[CapTableGroup, ...] = ()
    seed: ScenarioSeed | None = None

    @property
    def total(self) -> int:
        seed = self.seed.shares if self.seed else 0
        return self.founder + self.pool + sum(g.shares for g in self.others) + seed


class Scenario(_Frozen):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    available_in: Literal["v1", "v3"]
    starting_equity_account: str  # credited when starting cash is posted on turn 0
    cap_table: ScenarioCapTable  # M4 (formulas.md 14.2)

    @property
    def selectable(self) -> bool:
        """Only v1 scenarios can be started in this release."""
        return self.available_in == "v1"


# --- People seed files (M1a) ----------------------------------------------------------------

_KEY = r"^[a-z][a-z0-9_]*$"
type Version = Literal["v1", "v3"]


class SkillDef(_Frozen):
    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
    short_label: str = Field(min_length=1)  # narrow table columns (People "Top skills")
    group: Literal["technical", "business", "leadership"]


class SkillsFile(_Frozen):
    skills: tuple[SkillDef, ...] = Field(min_length=1)


class TraitDef(_Frozen):
    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)


class HiddenTraitDef(_Frozen):
    key: str = Field(pattern=_KEY)


class PersonalityFile(_Frozen):
    personality: tuple[TraitDef, ...] = Field(min_length=1)
    hidden: tuple[HiddenTraitDef, ...] = Field(min_length=1)
    work_styles: tuple[TraitDef, ...] = Field(min_length=1)


class InterestsFile(_Frozen):
    interests: tuple[TraitDef, ...] = Field(min_length=1)


class Region(_Frozen):
    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
    salary_multiplier_bp: int = Field(gt=0)


class RegionsFile(_Frozen):
    regions: tuple[Region, ...] = Field(min_length=1)


class CityDef(_Frozen):
    """A named tech hub (formulas.md 19.1, M9)."""

    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
    region: str
    salary_multiplier_bp: int = Field(gt=0)
    rent_index: float = Field(gt=0)
    talent_weight: float = Field(ge=0)
    talent: dict[str, float] = Field(default_factory=dict)  # skill group or skill -> points


class CitiesFile(_Frozen):
    cities: tuple[CityDef, ...] = Field(min_length=1)
    region_growth: dict[str, float]
    home_city_region: dict[str, str] = Field(default_factory=dict)


type ProductFunction = Literal["builder", "seller", "marketer", "none"]  # formulas.md 11.3


class Role(_Frozen):
    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
    product_function: ProductFunction
    summary: str = Field(min_length=1)  # M10b (23.4): what the role does
    why_hire: str = Field(min_length=1)  # M10b (23.4): when to hire one
    primary: tuple[str, ...] = Field(min_length=1)
    secondary: tuple[str, ...]
    work_style: str
    work_style_weights: dict[str, float]
    interest_weights: dict[str, float]
    salary_band_mid_cents: dict[str, int]

    @model_validator(mode="after")
    def _check(self) -> Role:
        skills = self.primary + self.secondary
        if len(set(skills)) != len(skills):
            raise ValueError(f"role {self.key!r}: a skill is listed twice")
        for name, weights in (
            ("work_style_weights", self.work_style_weights),
            ("interest_weights", self.interest_weights),
        ):
            if any(w < 0 for w in weights.values()) or not any(w > 0 for w in weights.values()):
                raise ValueError(f"role {self.key!r}: {name} need a positive weight")
        if sorted(self.salary_band_mid_cents) != sorted(LEVELS):
            raise ValueError(f"role {self.key!r}: salary_band_mid_cents must cover {list(LEVELS)}")
        if any(v <= 0 for v in self.salary_band_mid_cents.values()):
            raise ValueError(f"role {self.key!r}: salary bands must be positive")
        return self


class RolesFile(_Frozen):
    roles: tuple[Role, ...] = Field(min_length=1)


class TagCondition(_Frozen):
    attr: str
    op: Literal[">=", "<="]
    value: float

    def holds(self, value: float) -> bool:
        return value >= self.value if self.op == ">=" else value <= self.value


class TagBoost(_Frozen):
    multiplier: float = Field(ge=0)
    when: tuple[TagCondition, ...] = Field(min_length=1)


class Tag(_Frozen):
    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
    base_bp: int = Field(ge=0)
    boost: TagBoost
    excludes: tuple[str, ...]
    reveal_text: str = Field(min_length=1)
    effect_note: str


class TagsFile(_Frozen):
    tags: tuple[Tag, ...] = Field(min_length=1)


class Background(_Frozen):
    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
    available_in: Version
    description: str = Field(min_length=1)
    bonuses: dict[str, float]
    default_allocation: dict[str, int]

    @property
    def selectable(self) -> bool:
        return self.available_in == "v1"


class PersonalityPreset(_Frozen):
    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)  # one line for the new-game preset card
    values: dict[str, float]


class BackgroundsFile(_Frozen):
    backgrounds: tuple[Background, ...] = Field(min_length=1)
    personality_presets: tuple[PersonalityPreset, ...] = Field(min_length=1)


class NamePool(_Frozen):
    first: tuple[str, ...] = Field(min_length=1)
    last: tuple[str, ...] = Field(min_length=1)


class NamesFile(_Frozen):
    names: dict[str, NamePool]
    companies: tuple[str, ...] = Field(min_length=1)  # rival startup names (M5, 15.4)


# --- Products and markets (M3): categories.yaml and incumbents.yaml -------------------------

type Reach = Literal["self_serve", "sales"]
WEIGHT_TOLERANCE = 1e-9  # tunable-exempt: float tolerance when checking that weights sum to 1


def _sums_to_one(values: Iterable[float]) -> bool:
    return abs(sum(values) - 1) < WEIGHT_TOLERANCE


class AppealWeights(_Frozen):
    quality: float = Field(ge=0)
    price: float = Field(ge=0)
    brand: float = Field(ge=0)
    features: float = Field(ge=0)

    @model_validator(mode="after")
    def _check(self) -> AppealWeights:
        if not _sums_to_one((self.quality, self.price, self.brand, self.features)):
            raise ValueError("appeal weights must sum to 1")
        return self


class SegmentDef(_Frozen):
    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
    weights: AppealWeights
    outside_option: float = Field(gt=0)
    base_churn: float = Field(ge=0, le=1)
    adoption: float = Field(ge=0, le=1)
    reach: Reach


class MarketDef(_Frozen):
    segment: str
    addressable: float = Field(gt=0)  # D0: customers in January 2010
    reference_price_cents: int = Field(gt=0)
    hosting_cents: int = Field(ge=0)


class CategoryDef(_Frozen):
    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
    growth: float = Field(ge=0)
    features_at_start: float = Field(gt=0)
    features_per_month: float = Field(ge=0)
    scope: float = Field(gt=0)
    brand_constant: float = Field(gt=0)
    dev_weights: dict[str, float]
    markets: tuple[MarketDef, ...] = Field(min_length=1)
    launch_quality: float | None = Field(default=None, ge=0, le=SCORE_MAX)  # M8: compliance
    # M8 (18.6): annual growth from each listed year on, instead of `growth`
    growth_by_year: dict[int, float] | None = None
    compute_indexed: bool = False  # M8: hosting x compute_index(year)

    def growth_in(self, year: int) -> float:
        """Annual demand growth in a calendar year: the latest growth_by_year entry at or
        before it, else `growth` (18.6)."""
        if not self.growth_by_year:
            return self.growth
        rate = self.growth
        for start in sorted(self.growth_by_year):
            if start <= year:
                rate = self.growth_by_year[start]
        return rate

    @model_validator(mode="after")
    def _check(self) -> CategoryDef:
        if self.growth_by_year is not None and any(g < 0 for g in self.growth_by_year.values()):
            raise ValueError(f"category {self.key!r}: growth_by_year must be >= 0")
        if any(w < 0 for w in self.dev_weights.values()) or not _sums_to_one(
            self.dev_weights.values()
        ):
            raise ValueError(f"category {self.key!r}: dev_weights must be >= 0 and sum to 1")
        if dupes := _dupes([m.segment for m in self.markets]):
            raise ValueError(f"category {self.key!r}: segments listed twice {dupes}")
        return self

    @property
    def segment_keys(self) -> tuple[str, ...]:
        return tuple(m.segment for m in self.markets)

    def market(self, segment: str) -> MarketDef:
        for m in self.markets:
            if m.segment == segment:
                return m
        raise KeyError(segment)


class RegionMarketDef(_Frozen):
    """A region as a market (formulas.md 19.5, M9)."""

    region: str
    size: float = Field(gt=0)  # x the home region's D0
    price_index: float = Field(gt=0)  # x p_ref
    neighbour: str  # sellers working there count neighbour_sellers in sales-led segments


class CategoriesFile(_Frozen):
    segments: tuple[SegmentDef, ...] = Field(min_length=1)
    categories: tuple[CategoryDef, ...] = Field(min_length=1)
    regions: tuple[RegionMarketDef, ...] = ()  # M9 (19.5)


class IncumbentSegment(_Frozen):
    price_cents: int = Field(gt=0)
    share_bp: int = Field(ge=0, le=BP_DENOMINATOR)


class IncumbentProduct(_Frozen):
    name: str = Field(min_length=1, max_length=80)  # tunable-exempt: name column width
    category: str
    quality: float = Field(ge=0, le=SCORE_MAX)
    features: float = Field(ge=0, le=SCORE_MAX)
    brand: float = Field(ge=0, le=SCORE_MAX)
    segments: dict[str, IncumbentSegment] = Field(min_length=1)
    regions: tuple[str, ...] | None = None  # M9 (19.5): None = north_america and europe


class IncumbentCompany(_Frozen):
    name: str = Field(min_length=1, max_length=80)  # tunable-exempt: name column width
    stage: int = Field(ge=0)
    founded_year: int
    personality: str  # M5 (15.1): one of PERSONALITIES
    builder_skill: float = Field(ge=1, le=20)  # tunable-exempt: attribute scale; pool skill d
    target_margin_bp: int = Field(ge=0, lt=BP_DENOMINATOR)  # margin its pools are sized for
    cash_months: float = Field(ge=0)  # starting cash in months of revenue (15.1)
    products: tuple[IncumbentProduct, ...] = Field(min_length=1)


DEFAULT_INCUMBENT_REGIONS = ("north_america", "europe")  # 19.5: v1 incumbents' regions


def incumbent_regions(product: IncumbentProduct) -> tuple[str, ...]:
    """The regions an incumbent product starts in (19.5)."""
    return product.regions if product.regions is not None else DEFAULT_INCUMBENT_REGIONS


class IncumbentsFile(_Frozen):
    companies: tuple[IncumbentCompany, ...]


class InvestorFirm(_Frozen):
    """One firm in investors.yaml (formulas.md 14.5). Its list index is its RNG key."""

    key: str = Field(pattern=_KEY)
    name: str = Field(min_length=1, max_length=80)  # tunable-exempt: name column width
    series: tuple[Series, ...] = Field(min_length=1)
    check_min_cents: int = Field(gt=0)
    check_max_cents: int = Field(gt=0)
    bias: float = Field(gt=0)
    response: float = Field(ge=0, le=1)
    patience: float
    from_year: int | None = None  # M10 (20.2): the first year it answers; None = always

    @model_validator(mode="after")
    def _check(self) -> InvestorFirm:
        if self.check_min_cents > self.check_max_cents:
            raise ValueError(f"{self.key}: check_min_cents exceeds check_max_cents")
        return self


type Instrument = Literal["venture_debt", "bank_loan"]
INSTRUMENTS: tuple[Instrument, ...] = ("venture_debt", "bank_loan")


class Lender(_Frozen):
    """A lender in investors.yaml (M10, formulas.md 20.3). The first lender offering the
    instrument in the year signs; nothing is drawn."""

    key: str = Field(pattern=_KEY)
    name: str = Field(min_length=1, max_length=80)  # tunable-exempt: name column width
    instrument: Instrument
    from_year: int | None = None
    until_year: int | None = None

    def offers(self, instrument: str, year: int) -> bool:
        return (
            self.instrument == instrument
            and (self.from_year is None or year >= self.from_year)
            and (self.until_year is None or year <= self.until_year)
        )


class InvestorsFile(_Frozen):
    firms: tuple[InvestorFirm, ...] = Field(min_length=1)
    lenders: tuple[Lender, ...] = ()  # M10


MONTHLY = 12  # tunable-exempt: months in a year, for the monthly history lists


class MacroHistory(_Frozen):
    """macro_history.yaml (M10, formulas.md 20.1): the base rate and consumer confidence by
    month and the venture climate by year, from `first_year` through the last year listed.
    The AI compute index's history is compute_index.yaml (18.6)."""

    first_year: int
    confidence_base_years: tuple[int, int]
    climate: dict[int, float]
    base_rate: dict[int, tuple[float, ...]]
    confidence: dict[int, tuple[float, ...]]

    @model_validator(mode="after")
    def _check(self) -> MacroHistory:
        years = list(range(self.first_year, self.last_year + 1))
        for name, table in (
            ("climate", self.climate),
            ("base_rate", self.base_rate),
            ("confidence", self.confidence),
        ):
            if sorted(table) != years:
                raise ValueError(f"{name} must list every year {years[0]}-{years[-1]}")
        for name, monthly in (("base_rate", self.base_rate), ("confidence", self.confidence)):
            if any(len(v) != MONTHLY for v in monthly.values()):
                raise ValueError(f"{name} needs 12 monthly values a year")
        if any(v <= 0 for v in self.climate.values()) or any(
            x <= 0 for v in self.confidence.values() for x in v
        ):
            raise ValueError("climate and confidence must be positive")
        if any(x < 0 for v in self.base_rate.values() for x in v):
            raise ValueError("base_rate must not be negative")
        lo, hi = self.confidence_base_years
        if not self.first_year <= lo <= hi <= self.last_year:
            raise ValueError("confidence_base_years must lie inside the history")
        return self

    @property
    def last_year(self) -> int:
        return max(self.climate)

    @property
    def confidence_base(self) -> float:
        """The raw confidence average over the base years (rescaled to 100)."""
        lo, hi = self.confidence_base_years
        values = [x for y in range(lo, hi + 1) for x in self.confidence[y]]
        return sum(values) / len(values)


class ComputeIndexFile(_Frozen):
    """AI compute price index by calendar year (formulas.md 18.6): `base` in `base_year`,
    then each year's multiplier on the year before (`changes`, else `default_change`)."""

    base_year: int
    base: float = Field(gt=0)
    default_change: float = Field(gt=0)
    changes: dict[int, float]

    @model_validator(mode="after")
    def _check(self) -> ComputeIndexFile:
        if any(v <= 0 for v in self.changes.values()):
            raise ValueError("compute_index changes must be positive")
        if any(y <= self.base_year for y in self.changes):
            raise ValueError("compute_index changes must be after base_year")
        return self

    def of(self, year: int) -> float:
        value = self.base
        for y in range(self.base_year + 1, year + 1):
            value *= self.changes.get(y, self.default_change)
        return value


class EntrantDef(_Frozen):
    """A named rival startup founded in its real month (formulas.md 18.7)."""

    name: str = Field(min_length=1, max_length=80)  # tunable-exempt: name column width
    year: int
    month: int = Field(ge=1, le=12)  # tunable-exempt: calendar months
    personality: str
    cash_cents: int = Field(gt=0)
    staff: int = Field(ge=1)  # people, the founder included
    category: str
    segments: tuple[str, ...] = Field(min_length=1)


class EntrantsFile(_Frozen):
    entrants: tuple[EntrantDef, ...] = ()


class InboxTemplate(_Frozen):
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class InboxTemplatesFile(_Frozen):
    templates: dict[str, InboxTemplate]


# Template keys the engine emits (M1b). The loader fails if any is missing.
INBOX_TEMPLATE_KEYS = (
    "candidates_arrived",
    "offer_accepted",
    "offer_declined",
    "resigned",
    "retired",
    "employee_left",
    "fired",
    "culture_carrier_left",
    "tag_revealed",
    # "out_of_cash" (M1-M3) is no longer emitted: M4's "insolvent" replaces it (14.7).
    # M2a
    "unit_leader_left",
    "plan_paused",
    "plan_filled",
    "plan_activity",
    # M3a
    "product_launched",
    "first_customer",
    "arr_milestone",
    "sales_capacity_limited",
    "product_rotting",
    "product_understaffed",  # M10b (23.4): builders, but too few to hold quality
    "choices_month",  # M10b (23.2): the month's event choices and modifiers
    "retained",  # M10b (23.3): a counter-offer kept someone
    "exec_report",  # M10c (24.3)
    "exec_decisions",  # M10c (24.1)
    "exec_proposal",  # M10c (24.1)
    # M4a (formulas.md 14)
    "safe_filled",
    "safe_declined",
    "term_sheets_arrived",
    "no_term_sheets",
    "round_lapsed",
    "round_closed",
    "board_meeting",
    "board_warning",
    "founder_removed",
    "board_seat_empty",  # M4c: name a nominee to the empty common seat
    "nominee_left",  # M4c: the nominee left the company
    "rival_failed",  # M5: a rival went bankrupt (15.1); shown via market news, not the inbox
    "market_news",  # M5: the month's rival moves (15.5)
    "rival_approach",  # M5: a rival approached one of the player's people (15.6)
    "poach_accepted",  # M5: the employee took the rival's offer (15.6)
    "poach_declined",  # M5: the employee stayed (15.6)
    "insolvent",
    "bridge_offered",
    "bridge_lapsed",
    "bridge_funded",
    "bankrupt",
    "stage_from_funding",
    # M8 (formulas.md 18)
    "division_created",
    "exec_appointed",
    "exec_removed",
    "exec_left",
    # M10 (formulas.md 20.3)
    "loan_signed",
    "loan_repaid",
    "covenant_breached",
    "loan_called",
    "office_leased",  # M9
    "office_closed",
    "region_launched",
    "region_live",
)


def _dupes(keys: list[str]) -> list[str]:
    return sorted({k for k in keys if keys.count(k) > 1})


class GameData(_Frozen):
    accounts: tuple[Account, ...]
    scenarios: tuple[Scenario, ...]
    skills: tuple[SkillDef, ...]
    personality: tuple[TraitDef, ...]
    hidden: tuple[HiddenTraitDef, ...]
    work_styles: tuple[TraitDef, ...]
    interests: tuple[TraitDef, ...]
    regions: tuple[Region, ...]
    roles: tuple[Role, ...]
    tags: tuple[Tag, ...]
    backgrounds: tuple[Background, ...]
    personality_presets: tuple[PersonalityPreset, ...]
    names: dict[str, NamePool]
    inbox_templates: dict[str, InboxTemplate]
    segments: tuple[SegmentDef, ...]
    categories: tuple[CategoryDef, ...]
    incumbents: tuple[IncumbentCompany, ...]
    investors: tuple[InvestorFirm, ...] = ()  # M4
    lenders: tuple[Lender, ...] = ()  # M10 (20.3)
    macro_history: MacroHistory | None = None  # M10 (20.1); replaces M4's climate.yaml
    startup_names: tuple[str, ...] = ()  # M5: rival startup names (names.yaml companies)
    event_templates: tuple[EventTemplate, ...] = ()  # M6: events/*.yaml (formulas.md 16.4)
    compute_index: ComputeIndexFile = ComputeIndexFile(
        base_year=2010,  # tunable-exempt: empty default index
        base=1.0,
        default_change=1.0,
        changes={},
    )  # M8 (18.6)
    entrants: tuple[EntrantDef, ...] = ()  # M8 (18.7)
    cities: tuple[CityDef, ...] = ()  # M9 (19.1)
    region_growth: dict[str, float] = Field(default_factory=dict)  # M9 (19.5)
    home_city_region: dict[str, str] = Field(default_factory=dict)  # M9: regions without a city
    region_markets: tuple[RegionMarketDef, ...] = ()  # M9 (19.5), categories.yaml regions

    def event_template(self, template_id: str) -> EventTemplate:
        for template in self.event_templates:
            if template.id == template_id:
                return template
        raise KeyError(template_id)

    @model_validator(mode="after")
    def _check_references(self) -> GameData:
        problems: list[str] = []

        for label, keys in (
            ("accounts.yaml codes", [a.code for a in self.accounts]),
            ("scenarios.yaml ids", [s.id for s in self.scenarios]),
            ("skills.yaml keys", self.skill_keys),
            ("personality.yaml keys", self.personality_keys + self.hidden_keys),
            ("work style keys", self.work_style_keys),
            ("interests.yaml keys", self.interest_keys),
            ("regions.yaml keys", self.region_keys),
            ("roles.yaml keys", [r.key for r in self.roles]),
            ("tags.yaml keys", [t.key for t in self.tags]),
            ("backgrounds.yaml keys", [b.key for b in self.backgrounds]),
            ("personality preset keys", [p.key for p in self.personality_presets]),
            ("categories.yaml segment keys", [s.key for s in self.segments]),
            ("categories.yaml category keys", [c.key for c in self.categories]),
            ("incumbents.yaml company names", [c.name for c in self.incumbents]),
            ("investors.yaml firm keys", [f.key for f in self.investors]),
        ):
            if dupes := _dupes(keys):
                problems.append(f"duplicate {label}: {dupes}")

        equity = {a.code for a in self.accounts if a.type == "equity"}
        for scenario in self.scenarios:
            if scenario.starting_equity_account not in equity:
                problems.append(
                    f"scenario {scenario.id!r}: starting_equity_account "
                    f"{scenario.starting_equity_account!r} is not an equity account"
                )

        skills = set(self.skill_keys)
        traits = set(self.personality_keys)
        styles = set(self.work_style_keys)
        interests = set(self.interest_keys)

        def unknown(where: str, keys: Iterable[str], known: set[str], kind: str) -> None:
            missing = sorted(set(keys) - known)
            if missing:
                problems.append(f"{where}: unknown {kind} {missing}")

        for role in self.roles:
            where = f"roles.yaml {role.key!r}"
            unknown(where, role.primary + role.secondary, skills, "skills")
            unknown(where, [role.work_style], styles, "work style")
            if set(role.work_style_weights) != styles:
                problems.append(f"{where}: work_style_weights must cover {sorted(styles)}")
            if set(role.interest_weights) != interests:
                problems.append(f"{where}: interest_weights must cover {sorted(interests)}")

        tag_keys = {t.key for t in self.tags}
        excludes = {t.key: set(t.excludes) for t in self.tags}
        for tag in self.tags:
            where = f"tags.yaml {tag.key!r}"
            unknown(where, [c.attr for c in tag.boost.when], traits, "personality traits")
            unknown(where, tag.excludes, tag_keys, "tags")
            if tag.key in tag.excludes:
                problems.append(f"{where}: excludes itself")
            for other in tag.excludes:
                if other in excludes and tag.key not in excludes[other]:
                    problems.append(
                        f"tags.yaml: {tag.key!r} excludes {other!r} but not the other way round"
                    )

        for bg in self.backgrounds:
            where = f"backgrounds.yaml {bg.key!r}"
            unknown(where, bg.bonuses, skills, "skills")
            unknown(where, bg.default_allocation, skills, "skills")
        for preset in self.personality_presets:
            if set(preset.values) != traits:
                problems.append(
                    f"backgrounds.yaml preset {preset.key!r}: values must cover {sorted(traits)}"
                )

        if set(self.names) != set(self.region_keys):
            problems.append(f"names.yaml: regions must be exactly {sorted(self.region_keys)}")

        segment_keys = {s.key for s in self.segments}
        categories = {c.key: c for c in self.categories}
        for cat in self.categories:
            where = f"categories.yaml {cat.key!r}"
            unknown(where, cat.dev_weights, skills, "skills")
            unknown(where, cat.segment_keys, segment_keys, "segments")
        shares: dict[tuple[str, str, str], int] = {}
        for company in self.incumbents:
            for product in company.products:
                where = f"incumbents.yaml {company.name!r} {product.name!r}"
                found = categories.get(product.category)
                if found is None:
                    problems.append(f"{where}: unknown category {product.category!r}")
                    continue
                unknown(where, product.segments, set(found.segment_keys), "segments")
                regions = incumbent_regions(product)
                unknown(where, regions, set(self.region_keys), "regions")
                for region in regions:
                    for seg, value in product.segments.items():
                        key = (product.category, seg, region)
                        shares[key] = shares.get(key, 0) + value.share_bp
        for (cat_key, seg, region), total in sorted(shares.items()):
            if total > BP_DENOMINATOR:
                problems.append(
                    f"incumbents.yaml: starting shares in {cat_key}/{seg} ({region}) exceed 100%"
                )
        problems += self._geo_problems(skills)

        names = {c.name for c in self.incumbents}
        for entrant in self.entrants:  # M8 (18.7)
            where = f"entrants.yaml {entrant.name!r}"
            if entrant.name in names or entrant.name in self.startup_names:
                problems.append(f"{where}: name is taken")
            names.add(entrant.name)
            if entrant.personality not in PERSONALITIES:
                problems.append(f"{where}: unknown personality {entrant.personality!r}")
            found = categories.get(entrant.category)
            if found is None:
                problems.append(f"{where}: unknown category {entrant.category!r}")
                continue
            unknown(where, entrant.segments, set(found.segment_keys), "segments")
        for company in self.incumbents:
            if company.personality not in PERSONALITIES:
                problems.append(f"incumbents.yaml {company.name!r}: unknown personality")

        firm_keys = {f.key for f in self.investors}
        for scenario in self.scenarios:
            seed = scenario.cap_table.seed
            if seed is not None and seed.lead not in firm_keys:
                problems.append(
                    f"scenarios.yaml {scenario.id!r}: seed lead {seed.lead!r} "
                    "is not in investors.yaml"
                )

        missing = sorted(set(INBOX_TEMPLATE_KEYS) - set(self.inbox_templates))
        if missing:
            problems.append(f"inbox_templates.yaml: missing templates {missing}")

        if problems:
            raise ValueError("; ".join(problems))
        return self

    def _geo_problems(self, skills: set[str]) -> list[str]:
        """M9: cities, regional growth and regional markets (formulas.md 19.1, 19.5)."""
        problems: list[str] = []
        if not self.cities:
            return problems
        regions = set(self.region_keys)
        groups = {s.group for s in self.skills}
        if dupes := _dupes([c.key for c in self.cities]):
            problems.append(f"duplicate cities.yaml keys: {dupes}")
        for city in self.cities:
            where = f"cities.yaml {city.key!r}"
            if city.region not in regions:
                problems.append(f"{where}: unknown region {city.region!r}")
            bad = sorted(set(city.talent) - groups - skills)
            if bad:
                problems.append(f"{where}: unknown talent keys {bad}")
        if set(self.region_growth) != regions:
            problems.append(f"cities.yaml: region_growth must cover exactly {sorted(regions)}")
        with_city = {c.region for c in self.cities}
        for region in sorted(regions - with_city):
            if self.home_city_region.get(region) not in with_city:
                problems.append(
                    f"cities.yaml: region {region!r} has no city and no home_city_region"
                )
        if [m.region for m in self.region_markets] != self.region_keys:
            problems.append("categories.yaml: regions must list every region in regions.yaml order")
        for m in self.region_markets:
            if m.neighbour not in regions or m.neighbour == m.region:
                problems.append(f"categories.yaml region {m.region!r}: bad neighbour")
        return problems

    # --- Lookups -------------------------------------------------------------------------

    def city(self, key: str) -> CityDef:
        for city in self.cities:
            if city.key == key:
                return city
        raise KeyError(key)

    def has_city(self, key: str) -> bool:
        return any(c.key == key for c in self.cities)

    def region_city(self, region: str) -> str:
        """The first city of a region (19.1): v1 people's home city; a region without a
        city uses its home_city_region's first city."""
        region = self.home_city_region.get(region, region)
        for city in self.cities:
            if city.region == region:
                return city.key
        raise KeyError(region)

    def region_index(self, key: str) -> int:
        """Position in regions.yaml: the third part of a regional `market` key (19.5)."""
        return self.region_keys.index(key)

    def region_market(self, region: str) -> RegionMarketDef:
        for m in self.region_markets:
            if m.region == region:
                return m
        raise KeyError(region)

    @property
    def skill_keys(self) -> list[str]:
        return [s.key for s in self.skills]

    @property
    def personality_keys(self) -> list[str]:
        return [t.key for t in self.personality]

    @property
    def hidden_keys(self) -> list[str]:
        return [t.key for t in self.hidden]

    @property
    def work_style_keys(self) -> list[str]:
        return [t.key for t in self.work_styles]

    @property
    def interest_keys(self) -> list[str]:
        return [t.key for t in self.interests]

    @property
    def region_keys(self) -> list[str]:
        return [r.key for r in self.regions]

    def scenario(self, scenario_id: str) -> Scenario | None:
        for scenario in self.scenarios:
            if scenario.id == scenario_id:
                return scenario
        return None

    def account_codes(self) -> frozenset[str]:
        return frozenset(a.code for a in self.accounts)

    def role(self, key: str) -> Role:
        for role in self.roles:
            if role.key == key:
                return role
        raise KeyError(key)

    def region(self, key: str) -> Region:
        for region in self.regions:
            if region.key == key:
                return region
        raise KeyError(key)

    def background(self, key: str) -> Background | None:
        for bg in self.backgrounds:
            if bg.key == key:
                return bg
        return None

    def firm(self, key: str) -> InvestorFirm:
        for firm in self.investors:
            if firm.key == key:
                return firm
        raise KeyError(key)

    def firm_index(self, key: str) -> int:
        """The firm's position in investors.yaml: its key in the finance stream (ADR-0018)."""
        for i, firm in enumerate(self.investors):
            if firm.key == key:
                return i
        raise KeyError(key)

    def category(self, key: str) -> CategoryDef:
        for cat in self.categories:
            if cat.key == key:
                return cat
        raise KeyError(key)

    def segment(self, key: str) -> SegmentDef:
        for seg in self.segments:
            if seg.key == key:
                return seg
        raise KeyError(key)

    def category_index(self, key: str) -> int:
        """Position in categories.yaml: the first part of the `market` stream key (ADR-0017)."""
        return [c.key for c in self.categories].index(key)

    def segment_index(self, key: str) -> int:
        """Position in the categories.yaml segments: the second part of the `market` key."""
        return [s.key for s in self.segments].index(key)

    def preset(self, key: str) -> PersonalityPreset | None:
        for preset in self.personality_presets:
            if preset.key == key:
                return preset
        return None
