"""The campaign's length and dynasty years (M37, formulas.md 52.1-52.6)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EraWindowOut(BaseModel):
    key: str
    label: str
    window_label: str = Field(description="The public window, e.g. 2040-2048")
    arrived_label: str | None = None


class LeaderChangeOut(BaseModel):
    company_id: int
    company_name: str
    date_label: str
    old_name: str | None
    new_name: str
    how: str = Field(description="heir | insider | outside")
    personality_changed: bool


class DeathOut(BaseModel):
    person_id: int
    name: str
    date_label: str
    age: int
    role: str = Field(description="head | member | adviser")


class CampaignOut(BaseModel):
    length: str = Field(description="standard | dynasty | endless (M52)")
    end_label: str = Field(description="The month the game ends after, or 'no end'")
    endless: bool = Field(default=False, description="M52 (66.3): a sandbox with no end")
    can_continue_sandbox: bool = Field(
        default=False, description="M52 (66.3): over after December 2069: continue in sandbox"
    )
    at_end: bool = Field(description="A standard campaign at December 2039: end or continue")
    can_switch: bool = Field(description="A standard campaign may still switch to dynasty")
    game_state: str
    founder_age: int | None
    dynasty_years: bool = Field(description="2040 or later")
    eras: list[EraWindowOut] = Field(description="Eras of dynasty years, once they are shown")
    leader_changes: list[LeaderChangeOut]
    deaths: list[DeathOut]


class CampaignActionOut(BaseModel):
    campaign: CampaignOut
