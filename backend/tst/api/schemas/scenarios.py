"""The Scenarios screen and the result screen's comparison (M51, formulas.md 63.3)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScorePartsOut(BaseModel):
    """The company score's five parts at the verdict, in points (30.1)."""

    value: float
    growth: float
    profit: float
    leadership: float
    reputation: float


class ScenarioResultOut(BaseModel):
    """One scenario save's verdict, from the app-wide results file."""

    save: str
    company: str
    result: str = Field(description="success | failure")
    date_label: str = Field(description="The game month of the verdict")
    score: int = Field(description="The company score at the verdict (30.1)")
    challenges: list[str]
    multiplier: float = Field(description="The challenge rules' score multipliers, multiplied")
    adjusted: int = Field(description="score x multiplier: what results are compared on")
    recorded_at: str = Field(description="When the verdict was kept (UTC, ISO 8601)")
    parts: ScorePartsOut | None = None


class ScenarioCardOut(BaseModel):
    key: str
    label: str
    description: str
    year: int
    goal: str
    deadline_label: str
    difficulty: str | None = Field(description="easy | medium | hard, from seeds 1-10's wins")
    sensible_wins: int | None = Field(description="The sensible script's wins on seeds 1-10")
    played: int = Field(description="Scenario saves with a verdict")
    best: ScenarioResultOut | None = Field(description="The best: a success, then the score")


class ScenariosOut(BaseModel):
    profile: str
    scenarios: list[ScenarioCardOut]
