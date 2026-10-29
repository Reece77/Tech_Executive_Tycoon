"""Pydantic schemas for balance and seed data (ADR-0008).

Model definitions only: this module never reads files. `tst.loader` parses the YAML and
validates it with these models. Unknown keys and out-of-range values fail validation.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.events.data import EFFECT_TYPES, SEVERITIES, TRIGGERS, VALUELESS, EventTemplate
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


ORG_TAGS = ("culture_carrier", "credit_taker", "toxic_high_performer")  # formulas.md 13.6
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


SERIES = ("seed", "a", "b")  # priced rounds in v1, in order (formulas.md 14.5)
type Series = Literal["seed", "a", "b"]


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

    @model_validator(mode="after")
    def _check(self) -> EventsBalance:
        counts, tolerance = 4, 1e-9  # tunable-exempt: 0-3 events (16.1), float tolerance
        if len(self.count_weights) != counts or abs(sum(self.count_weights) - 1) > tolerance:
            raise ValueError("events.count_weights: four probabilities (0-3 events) summing to 1")
        if sorted(self.trigger) != sorted(TRIGGERS):
            raise ValueError(f"events.trigger must cover exactly {list(TRIGGERS)}")
        sized = sorted(set(EFFECT_TYPES) - set(VALUELESS) - {"resign"})
        if sorted(self.caps) != sized:
            raise ValueError(f"events.caps must cover exactly {sized}")
        for effect, caps in self.caps.items():
            if len(caps) != len(SEVERITIES) or any(c <= 0 for c in caps) or caps != sorted(caps):
                raise ValueError(f"events.caps.{effect}: three rising positive caps")
        return self

    def cap(self, effect: str, severity: str) -> float:
        return self.caps[effect][SEVERITIES.index(severity)]


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


class Balance(_Frozen):
    company: CompanyBalance
    costs: CostsBalance  # M4c (formulas.md 8)
    scenario: dict[str, ScenarioBalance]
    difficulty: dict[str, DifficultyBalance]
    backup: BackupBalance
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


type ProductFunction = Literal["builder", "seller", "marketer", "none"]  # formulas.md 11.3


class Role(_Frozen):
    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
    product_function: ProductFunction
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

    @model_validator(mode="after")
    def _check(self) -> CategoryDef:
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


class CategoriesFile(_Frozen):
    segments: tuple[SegmentDef, ...] = Field(min_length=1)
    categories: tuple[CategoryDef, ...] = Field(min_length=1)


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


class IncumbentCompany(_Frozen):
    name: str = Field(min_length=1, max_length=80)  # tunable-exempt: name column width
    stage: int = Field(ge=0)
    founded_year: int
    personality: str  # M5 (15.1): one of PERSONALITIES
    builder_skill: float = Field(ge=1, le=20)  # tunable-exempt: attribute scale; pool skill d
    target_margin_bp: int = Field(ge=0, lt=BP_DENOMINATOR)  # margin its pools are sized for
    cash_months: float = Field(ge=0)  # starting cash in months of revenue (15.1)
    products: tuple[IncumbentProduct, ...] = Field(min_length=1)


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

    @model_validator(mode="after")
    def _check(self) -> InvestorFirm:
        if self.check_min_cents > self.check_max_cents:
            raise ValueError(f"{self.key}: check_min_cents exceeds check_max_cents")
        return self


class InvestorsFile(_Frozen):
    firms: tuple[InvestorFirm, ...] = Field(min_length=1)


class ClimateFile(_Frozen):
    """Funding climate by calendar year (formulas.md 14.3)."""

    default: float = Field(gt=0)
    years: dict[int, float]

    def of(self, year: int) -> float:
        return self.years.get(year, self.default)


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
    climate: ClimateFile = ClimateFile(default=1.0, years={})  # M4
    startup_names: tuple[str, ...] = ()  # M5: rival startup names (names.yaml companies)
    event_templates: tuple[EventTemplate, ...] = ()  # M6: events/*.yaml (formulas.md 16.4)

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
        shares: dict[tuple[str, str], int] = {}
        for company in self.incumbents:
            for product in company.products:
                where = f"incumbents.yaml {company.name!r} {product.name!r}"
                found = categories.get(product.category)
                if found is None:
                    problems.append(f"{where}: unknown category {product.category!r}")
                    continue
                unknown(where, product.segments, set(found.segment_keys), "segments")
                for seg, value in product.segments.items():
                    key = (product.category, seg)
                    shares[key] = shares.get(key, 0) + value.share_bp
        for (cat_key, seg), total in sorted(shares.items()):
            if total > BP_DENOMINATOR:
                problems.append(f"incumbents.yaml: starting shares in {cat_key}/{seg} exceed 100%")

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

    # --- Lookups -------------------------------------------------------------------------

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
