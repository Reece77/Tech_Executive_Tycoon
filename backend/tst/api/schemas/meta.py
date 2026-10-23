from __future__ import annotations

from pydantic import BaseModel


class ScenarioOut(BaseModel):
    id: str
    name: str
    description: str
    available_in: str
    selectable: bool
    starting_cash_cents: int  # at standard difficulty


class LabelOut(BaseModel):
    key: str
    label: str


class SkillMetaOut(BaseModel):
    key: str
    label: str
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
