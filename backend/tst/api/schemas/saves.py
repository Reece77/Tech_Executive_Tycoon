"""Request and response models for /api/saves. Money fields are integer cents (ADR-0009)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut, InboxItemOut
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
    mission: list[str] | None = Field(
        default=None, description="Two interests; omit for the founder's first two"
    )


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
    payroll_cents: int
    headcount: int
    avg_morale: float | None
    mrr_cents: int
    arr_cents: int
    founder_bp: int = Field(description="The founder's shares in bp of FD (M4a)")
    board_confidence: float | None = Field(description="Average director confidence (M4a)")


class CostLineOut(BaseModel):
    account: str
    label: str
    amount_cents: int


class TeamOut(BaseModel):
    """The team as it stands now (not at the last month end)."""

    headcount: int
    on_notice: int
    people_cost_cents: int = Field(description="Salaries, benefits and office this month")
    payroll_cents: int = Field(description="Salaries plus benefits this month")
    avg_morale: float | None = Field(description="Employees, not the founder; null if none")


class OrgTileOut(BaseModel):
    """The Overview's Org tile (M2b)."""

    units: int = Field(description="Departments and teams")
    managers_over_span: int
    manager_label: str | None = Field(
        description="strong | fine | stretched for the average manager morale term; null if none"
    )


class FundingTileOut(BaseModel):
    """The Overview's funding tile (M4b)."""

    last_round_label: str | None = Field(description="Series of the latest priced round")
    last_round_date_label: str | None
    post_money_cents: int | None
    founder_fraction: float = Field(description="The founder's share of fully diluted shares")
    board_label: str | None = Field(description="confident | watchful | losing patience")
    board_confidence: float | None
    safes_outstanding: int = Field(description="SAFEs that convert at the next priced round")


class StageReachedOut(BaseModel):
    stage: int
    stage_label: str
    turn: int
    date_label: str


class OverviewOut(BaseModel):
    save_id: str
    company_name: str
    turn: int
    date_label: str
    cash_cents: int
    monthly_burn_cents: int
    runway_months: int | None = Field(
        description="Whole months of cash at this month's projected costs; null if none"
    )
    history: list[SnapshotPointOut] = Field(description="Last 12 month-end snapshots, oldest first")
    stage: int
    stage_label: str
    runway_low: bool = Field(description="Runway is below the morale warning threshold")
    mission: list[str]
    headcount: int
    payroll_cents: int = Field(description="Salaries plus benefits in the last closed month")
    avg_morale: float | None = Field(description="Employees, not the founder; null if none")
    energy: EnergyOut
    unread_inbox: int
    costs_last_month: list[CostLineOut] = Field(description="Expenses posted last month")
    latest_inbox: list[InboxItemOut] = Field(description="Five newest inbox items")
    team: TeamOut
    month_costs: list[CostLineOut] = Field(
        description="This month's projected month-end costs at the current team and searches"
    )
    month_paid: list[CostLineOut] = Field(description="Expenses already posted this month")
    month_total_cents: int = Field(description="Projected plus already posted")
    option_pool_left_bp: int = Field(
        default=0, description="Option pool left: staff equity plus pending offers counted"
    )
    network_bonus_candidates: int = Field(
        default=0, description="Extra network candidates the founder's sociability brings"
    )
    org: OrgTileOut | None = None
    mrr_cents: int = Field(description="Revenue in the last closed month (M3a)")
    arr_cents: int = Field(description="12 x MRR")
    month_revenue_cents: int = Field(
        description="This month's revenue at the current customers and prices (M3b)"
    )
    game_state: str = Field(description="active | bankrupt | founder_removed (M4a)")
    ended_turn: int | None = Field(description="Turn the game ended; null while active")
    stage_since_turn: int | None = Field(
        description="Turn the current stage was reached; null if a pre-M4b save lacks it"
    )
    stage_since_label: str | None
    stage_history: list[StageReachedOut] = Field(description="Each stage reached, oldest first")
    funding: FundingTileOut
