"""Holiday request and response models (docs/formulas.md 17.1; M7b)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HolidayIn(BaseModel):
    months: int | None = Field(default=None, description="1 to max_months; omit for the default")
    stop: Literal["minor", "major", "critical"] | None = Field(
        default=None, description="Stop after an event at or above this severity"
    )


class HolidayOut(BaseModel):
    status: Literal["idle", "running", "finished", "failed"]
    months: int = Field(description="Months chosen (0 when idle)")
    months_done: int
    stop: str | None
    turn: int = Field(description="The save's current turn")
    date_label: str
    reason: str | None = Field(
        description="game_over | event | runway | offer | months | stopped, once finished"
    )
    reason_text: str | None
    summary_item_id: int | None = Field(description="The 'While you were away' inbox item")
    error: str | None
    stop_requested: bool
    max_months: int
    default_months: int
    default_stop: str
    stop_runway_months: int
