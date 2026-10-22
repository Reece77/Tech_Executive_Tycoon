"""Request and response models for /api/saves. Money fields are integer cents (ADR-0009)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.db.repository import MAX_STORED_SEED
from tst.sim.data_models import DEFAULT_DIFFICULTY
from tst.sim.people.founder import FounderSpec
from tst.sim.setup import DEFAULT_FOUNDER


class FounderIn(BaseModel):
    """Founder build (docs/formulas.md section 5). Omitted fields use the defaults."""

    background: str = DEFAULT_FOUNDER.background
    allocation: dict[str, int] | None = Field(
        default=None, description="Skill points to spend; omit for the background's default"
    )
    personality_preset: str | None = Field(default=None, description="Omit for random")
    age: int | None = None
    region: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    interests: list[str] | None = None
    work_style: str | None = None

    def to_spec(self) -> FounderSpec:
        return FounderSpec(
            background=self.background,
            allocation=self.allocation,
            personality_preset=self.personality_preset,
            age=self.age,
            region=self.region,
            first_name=self.first_name,
            last_name=self.last_name,
            interests=None if self.interests is None else tuple(self.interests),
            work_style=self.work_style,
        )


class CreateSaveIn(BaseModel):
    name: str = Field(min_length=1, max_length=64, description="Save slug: a-z, 0-9, - or _")
    seed: int | None = Field(
        default=None, ge=0, le=MAX_STORED_SEED, description="Omit to generate one"
    )
    scenario: str
    company_name: str = Field(min_length=1, max_length=80)
    difficulty: str = DEFAULT_DIFFICULTY
    founder: FounderIn | None = None


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
