"""Leaf schemas of the founder's life (M24, formulas.md 32.1, 32.6) that the overview, the
game over screen and the Hall of Fame embed (kept apart to avoid an import cycle)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CauseOut(BaseModel):
    turn: int
    date_label: str
    change: float
    cause: str


class StressOut(BaseModel):
    """The top bar's stress meter (32.1)."""

    stress: float = Field(description="0-100")
    burnout: bool
    burnout_at: float
    recover_below: float
    energy_cut_pct: float = Field(description="The monthly energy lost while burnt out, %")
    burnouts: int
    causes: list[CauseOut] = Field(description="The last months' changes, newest last")


class LegacyOut(BaseModel):
    """The legacy score with its parts (32.6), across every company the founder ran."""

    total: int
    best_score: int
    best_company: str | None
    giving: float
    persona: float
    grants_cents: int
    wealth: float = Field(0.0, description="M26 (37.5): points from net worth")
    net_worth_cents: int = Field(0, description="Net worth at the last month end")
