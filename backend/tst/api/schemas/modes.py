"""M15b schemas (docs/formulas.md 30): the company score."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreOut(BaseModel):
    """A company's score now (30.1), from public inputs only, with its parts in points."""

    score: int = Field(description="0-1,000")
    value_points: float
    growth_points: float
    profit_points: float
    leadership_points: float
    reputation_points: float
    estimate_cents: int = Field(
        description="Market cap if listed, else the displayed value range's midpoint (28.1)"
    )
    last_december: int | None = Field(description="The score at the last December, if any")


class RankingEntryOut(BaseModel):
    place: int
    company_id: int
    name: str
    is_you: bool
    value_label: str = Field(description="Revenue a year, or the list's 0-100 measure")


class RankingListOut(BaseModel):
    kind: str = Field(description="revenue | places | innovative")
    label: str
    entries: list[RankingEntryOut]


class RankingsOut(BaseModel):
    """The latest January's industry rankings (30.4)."""

    year: int | None = Field(description="The year they were published; null before the first")
    lists: list[RankingListOut]
    years: list[int] = Field(description="Every year with rankings, newest first")


class ContinueUntilOut(BaseModel):
    """Continue until something needs me (30.5)."""

    months_played: int
    stopped_for: str = Field(
        description="game_over | critical_event | event | pitch | proposal | promise | deal "
        "| months"
    )
    stopped_label: str
    turn: int
    date_label: str


class FoundAgainIn(BaseModel):
    """Found a new company after an exit (M15b addendum 10)."""

    company_name: str = Field(min_length=1, max_length=60)
    keep_cents: int = Field(default=0, ge=0, description="Proceeds the founder keeps")


class ExitChoiceOut(BaseModel):
    """After the choice: the game's state and the company the player now runs."""

    game_state: str = Field(description="active (founded again) | retired")
    company_id: int
    company_name: str
