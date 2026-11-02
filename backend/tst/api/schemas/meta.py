from __future__ import annotations

from pydantic import BaseModel, Field


class ScenarioOut(BaseModel):
    id: str
    name: str
    description: str
    available_in: str
    selectable: bool
    starting_cash_cents: int  # at standard difficulty
    starting_cash_by_difficulty: dict[str, int]


class LabelOut(BaseModel):
    key: str
    label: str


class SkillMetaOut(BaseModel):
    key: str
    label: str
    short_label: str
    group: str


class BackgroundOut(BaseModel):
    key: str
    label: str
    description: str
    available_in: str
    selectable: bool
    bonuses: dict[str, float]
    default_allocation: dict[str, int]


class PresetOut(BaseModel):
    key: str
    label: str
    description: str
    values: dict[str, float]


class FounderRulesOut(BaseModel):
    skill_base: float
    skill_points: int
    skill_cap: float
    age_min: int
    age_max: int
    default_age: int
    default_region: str
    mission_size: int


class NewGameMetaOut(BaseModel):
    scenarios: list[ScenarioOut]  # selectable ones
    difficulties: list[str]
    backgrounds: list[BackgroundOut]
    personality_presets: list[PresetOut]
    skills: list[SkillMetaOut]
    interests: list[LabelOut]
    work_styles: list[LabelOut]
    regions: list[LabelOut]
    roles: list[LabelOut]
    founder_rules: FounderRulesOut
    cities: list[LabelOut] = Field(default_factory=list, description="HQ choices (M9)")
    default_hq_city: str | None = None


class FounderSkillOut(BaseModel):
    key: str
    label: str
    group: str
    value: float


class FounderPreviewOut(BaseModel):
    skills: list[FounderSkillOut]
    points_spent: int
    points_remaining: int
    errors: list[str]


class ChannelOut(BaseModel):
    key: str  # network | job_post | recruiter | poach (M5)
    label: str
    energy: int
    monthly_cost_cents: int  # while open (job post)
    hire_fee_bp: int  # of first-year salary, charged on hire (recruiter)
    batch_min: int
    batch_max: int
    repeats: bool  # a new batch every month until closed
    level_mix: dict[str, int]  # percent by level


class RoleOut(BaseModel):
    key: str
    label: str
    primary_skills: list[str]
    secondary_skills: list[str]
    product_function: str = Field(description="builder, seller, marketer or none (11.3)")
    summary: str = Field(description="What the role does (23.4, M10b)")
    why_hire: str = Field(description="When to hire one (23.4, M10b)")


class HiringMetaOut(BaseModel):
    """Rules and costs the Recruitment and People screens display (formulas.md 6-8)."""

    channels: list[ChannelOut]
    roles: list[RoleOut]
    interview_energy: int
    reference_check_energy: int
    offer_energy: int
    max_offer_equity_bp: int
    lowball_ratio: float
    candidate_shelf_turns: int
    fire_morale_penalty_min: int  # morale points everyone else loses at least
    energy_per_month: int
