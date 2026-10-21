"""Request and response models for /api/saves. Money fields are integer cents (ADR-0009)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.db.repository import MAX_STORED_SEED
from tst.sim.data_models import DEFAULT_DIFFICULTY


class CreateSaveIn(BaseModel):
    name: str = Field(min_length=1, max_length=64, description="Save slug: a-z, 0-9, - or _")
    seed: int | None = Field(
        default=None, ge=0, le=MAX_STORED_SEED, description="Omit to generate one"
    )
    scenario: str
    company_name: str = Field(min_length=1, max_length=80)
    difficulty: str = DEFAULT_DIFFICULTY


class SaveOut(BaseModel):
    save_id: str
    company_name: str
    scenario_id: str
    difficulty: str
    turn: int
    date_label: str


class SnapshotPointOut(BaseModel):
    turn: int
    date_label: str
    cash_cents: int
    monthly_burn_cents: int


class OverviewOut(BaseModel):
    save_id: str
    company_name: str
    turn: int
    date_label: str
    cash_cents: int
    monthly_burn_cents: int
    runway_months: int | None = Field(description="Null when the company is not burning cash")
    history: list[SnapshotPointOut] = Field(description="Last 12 month-end snapshots, oldest first")
