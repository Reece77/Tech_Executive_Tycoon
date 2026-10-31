"""Divisions, executive seats, support coverage and division statements (M8, formulas.md
18.8). Seat fit and effects are estimates from displayed ranges; never s or e."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class DivisionOut(BaseModel):
    unit_id: int
    name: str
    president_id: int | None
    president_name: str | None
    services: str = Field(description="central | embedded (18.4)")
    headcount: int
    unit_ids: list[int] = Field(description="The departments and teams under it")
    product_ids: list[int]
    product_names: list[str]
    operating_profit_cents: int | None = Field(
        description="Last month's operating profit after shared services; null before a month"
    )
    effect_note: str = Field(description="Its main structural effect, in words")


class SupportPoolOut(BaseModel):
    key: str = Field(description="central, or the embedded division's id")
    label: str
    headcount: int
    support_staff: int
    needed: int = Field(description="Support staff for full coverage: one per 15 staff")
    covered: bool
    output_effect_pct: float = Field(
        description="Change to output, capacity and marketing, %; an estimate: the COO's effect "
        "from displayed ranges (18.8)"
    )
    morale_effect: float = Field(description="Morale points from 'Admin and support'")


class CrossDivisionOut(BaseModel):
    product_id: int
    product_name: str
    division_names: list[str]
    output_effect_pct: float
    fix: str = Field(description="The move that removes the factor")


class SeatOut(BaseModel):
    seat: str = Field(description="coo | cfo | cto | cpo | cmo | cro")
    label: str
    effect_label: str = Field(description="What the seat changes, e.g. 'builder output'")
    holder_id: int | None
    holder_name: str | None
    fit: str | None = Field(description="Fit as words from what you know: strong, fair, weak")
    estimated_effect_pct: float | None = Field(
        description="Estimated change from displayed midpoints (est.); for COO, on the layer "
        "tax and support shortfall"
    )
    vacancy_penalty_pct: float | None = Field(description="The penalty while vacant (stage 3+)")


class ScaleupOut(BaseModel):
    stage: int
    in_play: bool = Field(description="Stage 3 or later: divisions, seats and support apply")
    unlock_stage: int
    max_divisions: int
    divisions: list[DivisionOut]
    support: list[SupportPoolOut]
    support_rule: str
    cross_division: list[CrossDivisionOut]
    seats: list[SeatOut]
    note: str


class ScaleupActionOut(BaseModel):
    scaleup: ScaleupOut
    energy: EnergyOut
    unread_inbox: int


class SharedServicesIn(BaseModel):
    services: str = Field(description="central | embedded")


class ProductDivisionIn(BaseModel):
    division_id: int | None = Field(description="Null makes the product corporate")


class AppointIn(BaseModel):
    person_id: int


class AppointCandidateOut(BaseModel):
    person_id: int
    name: str
    role: str
    level: str
    fit: str
    estimated_effect_pct: float
    problem: str | None = Field(description="Why they cannot take the seat now, or null")


class SeatCandidatesOut(BaseModel):
    seat: SeatOut
    candidates: list[AppointCandidateOut]
    energy_cost: int
    note: str


class DivisionColumnOut(BaseModel):
    division_id: int | None = Field(description="Null for corporate or the company")
    name: str
    embedded: bool
    headcount: int
    revenue_cents: int
    salaries_benefits_cents: int
    hosting_cents: int
    marketing_cents: int
    office_cents: int
    tools_ga_cents: int
    direct_profit_cents: int
    shared_services_cents: int = Field(
        description="Negative for a central division, positive for corporate, 0 if embedded"
    )
    operating_profit_cents: int
    operating_margin: float | None
    revenue_growth_12m: float | None = Field(description="Last 12 months against the 12 before")


class DivisionPeriodOut(BaseModel):
    first_turn: int
    last_turn: int
    label: str
    columns: list[DivisionColumnOut] = Field(description="Corporate, each division, Company")


class DivisionStatementsOut(BaseModel):
    period: str
    periods: list[DivisionPeriodOut] = Field(description="Newest first")
