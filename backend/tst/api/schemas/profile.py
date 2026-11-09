"""Achievements (M25 section 2): the profile's earned, locked and hidden achievements."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AchievementOut(BaseModel):
    key: str
    title: str = Field(description='"???" for a hidden achievement not yet earned')
    description: str
    hidden: bool
    earned: bool
    save: str | None = Field(default=None, description="The save it was earned in")
    company: str | None = None
    date_label: str | None = Field(default=None, description="The game date it was earned")
    seen: bool = True


class AchievementsOut(BaseModel):
    profile: str
    earned: int
    total: int
    achievements: list[AchievementOut]
    unseen: list[AchievementOut] = Field(description="Earned and not yet shown as a toast")
    eligible: bool = Field(default=True, description="Whether this save can earn any")
    reason: str | None = Field(default=None, description="Why this save earns none")


class SeenIn(BaseModel):
    keys: list[str]
