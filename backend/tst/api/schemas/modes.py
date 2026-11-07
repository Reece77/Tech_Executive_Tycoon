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
