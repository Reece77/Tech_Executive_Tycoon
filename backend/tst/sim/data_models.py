"""Pydantic schemas for balance and seed data (ADR-0008).

Model definitions only: this module never reads files. `tst.loader` parses the YAML and
validates it with these models. Unknown keys and out-of-range values fail validation.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# ---------------------------------------------------------------------------
# balance.yaml
# ---------------------------------------------------------------------------


class CompanyBalance(_Frozen):
    base_monthly_cost_cents: int = Field(ge=0)


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
    pa_phrase_bounds: tuple[float, ...]

    @model_validator(mode="after")
    def _check(self) -> RevealBalance:
        if sorted(self.strength) != sorted(REVEAL_ACTIONS):
            raise ValueError(f"strength must define exactly {list(REVEAL_ACTIONS)}")
        if any(not 0 <= s <= 1 for s in self.strength.values()):
            raise ValueError("strength values must be fractions in [0, 1]")
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


ENERGY_ACTIONS = ("interview", "reference_check", "job_post", "recruiter", "network", "offer")
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
    option_pool_bp: int = Field(ge=0)
    offer: OfferBalance

    @model_validator(mode="after")
    def _check(self) -> HiringBalance:
        if sorted(self.channel) != sorted(CHANNELS):
            raise ValueError(f"channel must define exactly {list(CHANNELS)}")
        if self.max_offer_equity_bp > self.option_pool_bp:
            raise ValueError("max_offer_equity_bp must not exceed option_pool_bp")
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


class Balance(_Frozen):
    company: CompanyBalance
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


class Scenario(_Frozen):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    available_in: Literal["v1", "v3"]
    starting_equity_account: str  # credited when starting cash is posted on turn 0

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


class Role(_Frozen):
    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
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
    "out_of_cash",
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

    def preset(self, key: str) -> PersonalityPreset | None:
        for preset in self.personality_presets:
            if preset.key == key:
                return preset
        return None
