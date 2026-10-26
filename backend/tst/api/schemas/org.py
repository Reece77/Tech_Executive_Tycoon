"""Organization, raises, hiring plans and morale breakdown schemas (M2a).

Never carry true attributes or unnoticed tags (ADR-0007, formulas.md 13.11). Span numbers
(L, S) and the manager morale term are shown, as the brief and 13.11 allow.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class OrgMemberOut(BaseModel):
    person_id: int
    name: str
    role_label: str
    level: str
    is_founder: bool
    is_leader: bool = Field(description="Leads this unit (the founder leads the company)")
    manager_id: int | None = Field(description="Null for the founder")
    remote: bool = Field(description="Works under a remote policy (no office fee)")


class UnitOut(BaseModel):
    unit_id: int | None = Field(description="Null for the company root")
    kind: str  # company | department | team
    name: str
    parent_id: int | None
    leader_id: int | None
    leader_name: str | None
    policy: str | None = Field(description="Own policy (office | remote); null = inherited")
    effective_policy: str
    members: list[OrgMemberOut]
    child_unit_ids: list[int]
    headcount: int = Field(description="People in this unit and every unit below it")


class ManagerOut(BaseModel):
    person_id: int
    name: str
    leads_unit_id: int | None = Field(description="Unit they lead; null for the founder")
    reports: list[int] = Field(description="Direct reports' person ids")
    span_limit: int = Field(description="L: reports handled comfortably (formulas.md 13.2)")
    span_factor: float = Field(description="S: 1 up to L reports, else L / n")
    over_span: bool
    label: str = Field(description="strong | fine | stretched, from their manager morale term")


class OrgOut(BaseModel):
    units: list[UnitOut] = Field(description="The company root first, then units by id")
    managers: list[ManagerOut]
    headcount: int
    departments_unlocked: bool
    managers_over_span: int


class CreateUnitIn(BaseModel):
    kind: str  # department | team
    name: str = Field(min_length=1, max_length=64)
    parent_id: int | None = None


class MoveUnitIn(BaseModel):
    parent_id: int | None = Field(description="A department, or null for the company root")


class RenameUnitIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class SetLeaderIn(BaseModel):
    person_id: int | None = Field(description="Null removes the current leader")


class MovePersonIn(BaseModel):
    unit_id: int | None = Field(description="Null moves them to the company root")


class SetPolicyIn(BaseModel):
    unit_id: int | None = Field(description="Null sets the company root's policy")
    policy: str | None = Field(description="office | remote; null inherits (units only)")


class OrgChangeIn(BaseModel):
    """One reorganization to preview; fields as for the matching action endpoint."""

    # create_unit | dissolve_unit | rename_unit | move_unit | set_leader | move_person | set_policy
    change: str
    unit_id: int | None = None
    person_id: int | None = None
    kind: str | None = None
    name: str | None = None
    parent_id: int | None = None
    policy: str | None = None


class MoraleChangeOut(BaseModel):
    person_id: int
    name: str
    change: float = Field(description="One-off morale points (formulas.md 13.7, 13.8)")


class ChangePreviewOut(BaseModel):
    allowed: bool
    problem: str | None = Field(description="Why the change is refused, if it is")
    energy_cost: int
    morale_changes: list[MoraleChangeOut]


class OrgActionOut(BaseModel):
    org: OrgOut
    energy: EnergyOut
    unread_inbox: int


class RaiseIn(BaseModel):
    salary_cents: int = Field(gt=0)


class PayPreviewOut(BaseModel):
    """A raise or promotion before it happens, from known values only."""

    allowed: bool
    problem: str | None
    energy_cost: int
    level: str
    new_level: str
    salary_cents: int
    new_salary_cents: int
    market_rate_cents: int = Field(description="Band mid for the current level and region")
    new_market_rate_cents: int = Field(description="Band mid for the level after the change")
    pay_term: float = Field(description="Pay term of the morale target now (formulas.md 9)")
    new_pay_term: float
    salary_change_bp: int = Field(description="New salary against the old, in bp (+530 = +5.3%)")
    market_ratio: float = Field(description="Salary / market rate now")
    new_market_ratio: float = Field(description="New salary / the new level's market rate")
    monthly_cost_change_cents: int = Field(description="Change in salary plus benefits a month")
    below_market: bool = Field(description="The new salary is below the new market rate")
    morale_change: float = Field(description="One-off morale points (formulas.md 13.8)")


class PlanActivityOut(BaseModel):
    turn: int
    date_label: str
    searches: int
    interviews: int
    scouted: int
    offers: int
    summary: str


class HiringPlanOut(BaseModel):
    plan_id: int
    owner_id: int
    owner_name: str
    owner_role_label: str
    owner_on_staff: bool = Field(description="False once the owner has left (the plan pauses)")
    unit_id: int | None
    unit_name: str
    role: str
    role_label: str
    target: int
    hired: int
    pending_offers: int
    channel: str  # job_post | recruiter | network | any
    ratio_bp: int
    equity_bp: int
    focus: str = Field(description='current ("Best now") | potential ("Spot potential")')
    status: str  # active | paused | filled | closed
    created_turn: int
    owner_energy: int | None = Field(description="The delegate's energy left this month")
    last_activity: PlanActivityOut | None


class HiringPlanIn(BaseModel):
    owner_id: int
    role: str
    target: int = Field(ge=1)
    channel: str = "any"
    ratio_bp: int = Field(gt=0)
    equity_bp: int = Field(default=0, ge=0)
    unit_id: int | None = None
    focus: str = "current"  # current | potential


class HiringPlanPatchIn(BaseModel):
    """Fields to change; omitted fields keep their value. `unit_id: null` means the root."""

    owner_id: int | None = None
    role: str | None = None
    target: int | None = Field(default=None, ge=1)
    channel: str | None = None
    ratio_bp: int | None = Field(default=None, gt=0)
    equity_bp: int | None = Field(default=None, ge=0)
    unit_id: int | None = None
    focus: str | None = None  # current | potential


class MoraleTermOut(BaseModel):
    key: str  # base | pay | fit | runway | manager | remote | teammate:<tag> | other
    label: str
    value: float


class MoraleBreakdownOut(BaseModel):
    """Why someone's morale is heading where it is (formulas.md 9, 13.11).

    Terms the company cannot know (unnoticed teammate tags, unrevealed interests) are summed
    into "other", so morale never reveals a hidden tag.
    """

    person_id: int
    morale: float
    target: float
    rate: float = Field(description="Share of the gap to target closed each month")
    terms: list[MoraleTermOut]
    manager_id: int | None
    manager_name: str | None


class OrgMetaOut(BaseModel):
    energy_costs: dict[str, int]
    department_unlock_headcount: int
    department_unlock_stage: int
    unit_kinds: list[str]
    policies: list[str]
    plan_channels: list[str]
    max_ratio_bp: int
    max_offer_equity_bp: int
    delegate_energy_per_month: int
    scout_energy: int
    raise_threshold_bp: int
    raise_cooldown_turns: int
    raise_morale: float
    pay_cut_morale: float
    promote_morale: float
    reorg_morale: dict[str, float]
    promotion_levels: list[str]
