"""Automation everywhere (M27a, formulas.md 40.8, 40.11): areas, owners, eligibility, fit
bands, limits, priorities, energy, decisions, proposals, digests and records. Never a true
skill or score, the quality probability, a draw, or which option was best."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class CandidateOut(BaseModel):
    person_id: int
    name: str
    role: str
    kind: Literal["seat", "ceo", "lead", "subsidiary_ceo"]
    fit: str = Field(description="weak fit, fair fit or strong fit, from displayed ranges")
    energy_left: int = Field(description="Automation energy a month left after their areas")


class AreaOut(BaseModel):
    area: str
    label: str
    seat: str | None
    status: Literal["manage", "automated", "cant"]
    reason: str | None = Field(None, description="Can't automate yet: why, and how to fix it")
    owner: CandidateOut | None = None
    candidates: list[CandidateOut]
    limit_cents: int | None = None
    priority: int | None = None
    answer_events: bool = True
    allow_bold: bool = False
    events: bool = Field(description="The area answers routine events of its categories")
    energy: int = Field(description="Energy an owner spends a month running it")
    decisions: int = Field(description="Decisions this month")
    mistakes: int = Field(description="Visible missteps this month")
    proposals_waiting: int
    no_time: bool
    over_budget: bool
    screen: str = Field(description="The front-end path of the area's own screen")


class AutomationOut(BaseModel):
    company_id: int
    company_name: str
    areas: list[AreaOut]
    default_limit_cents: int
    stop_for_approvals: bool


class AssignmentOut(BaseModel):
    area: str
    label: str
    person_id: int
    name: str
    fit: str
    limit_cents: int


class AutomatePlanOut(BaseModel):
    assignments: list[AssignmentOut]
    left_out: list[str] = Field(description="Areas nobody can run yet")


class AreaOwnerIn(BaseModel):
    area: str
    person_id: int
    limit_cents: int | None = Field(None, ge=0)
    priority: int | None = Field(None, ge=0)


class AreaIn(BaseModel):
    area: str


class AreaSettingsIn(BaseModel):
    area: str
    limit_cents: int | None = Field(None, ge=0)
    priority: int | None = Field(None, ge=0)
    answer_events: bool | None = None
    allow_bold: bool | None = None


class AutomateAllIn(BaseModel):
    """The plan the player confirmed (from GET automation/plan)."""

    assignments: list[AreaOwnerIn]


class AutomationActionOut(BaseModel):
    automation: AutomationOut
    energy: EnergyOut
    unread_inbox: int


class KpiOut(BaseModel):
    key: str
    label: str
    now: int
    last: int | None
    target: int | None
    money: bool
    text: str


class DigestAreaOut(BaseModel):
    area: str
    label: str
    person_id: int
    owner: str
    did: int
    lines: list[str]
    committed_cents: int
    limit_cents: int
    mistakes: list[str]
    proposals: list[int]
    kpis: list[KpiOut]
    notes: list[str]


class DigestOut(BaseModel):
    turn: int
    month: str
    opening: str
    areas: list[DigestAreaOut]
    attention: list[str]
    quarter_reports: bool
    inbox_item_id: int | None = None
    items: list[int] = Field(
        default_factory=list, description="Inbox items the automated areas produced this month"
    )


class RecordOut(BaseModel):
    """An owner's record (40.3): outcomes only."""

    person_id: int
    name: str
    areas: list[str]
    decisions_year: int
    mistakes_year: int
    proposals: int
    proposals_approved: int
    proposals_declined: int
    proposals_expired: int
    pitches_hit: int
    pitches_missed: int
    recent: list[str]
