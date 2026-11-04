"""Divisions, executive seats, support coverage and division statements (M8, formulas.md
18.8). Seat fit and effects are estimates from displayed ranges; never s or e."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut, PitchRecordOut


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


class GuardChoiceOut(BaseModel):
    """One value a list guardrail may hold (M13b): a unit, a product or a category."""

    value: str = Field(description="The id or key as a string")
    label: str


class AuthorityOut(BaseModel):
    """A seat's authority (24.1, M10c): on or off and its guardrails. Never the decision
    quality or the holder's score (24.4)."""

    enabled: bool
    guardrails: dict[str, float | list[int] | list[str]] = Field(
        description="headcount_cap, max_salary_ratio_bp, protected_units (CTO), price_band_pct "
        "(CRO), marketing_pct_of_revenue (CMO), coverage_target and lease_approval_rent_cents "
        "(COO), runway_months and repay_above_months (CFO), headcount_cap, categories and "
        "protected_products (CPO, M13b)"
    )
    choices: dict[str, list[GuardChoiceOut]] = Field(
        default_factory=dict,
        description="For each list guardrail, the values it may hold (M13b)",
    )
    since_label: str | None = Field(description="Given since; null while off")
    acts_on: str = Field(description="What the seat does with authority")


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
    authority: AuthorityOut | None = Field(
        description="Authority over the seat's function (M10c, 24.1; the CPO's from M13b)"
    )
    record: PitchRecordOut | None = Field(
        default=None, description="The holder's pitch record (27.1, M13b)"
    )


class PitchOut(BaseModel):
    """A big move an executive proposes (27.1, M13b), with the numbers they pitch it on:
    estimates from what the company sees. Never the pitch probability, the quality draw, the
    executive's true ambition, skills or score, or which candidate was best (27.6)."""

    pitch_id: int
    seat: str = Field(description="cpo | cro | cto | coo | cmo | cfo | ceo")
    person_id: int
    name: str
    date_label: str
    kind: str = Field(
        description="new_product | sunset | region | research | data_centre | office | plant "
        "| campaign | buyback"
    )
    title: str
    why: str
    cost_cents: int = Field(description="Its cost over 12 months: the auto-approve test")
    capex_cents: int
    monthly_cents: int
    hires: int
    unit: str = Field(description="cents_month | cents | points | people | customers")
    low: int = Field(description="The low case at 24 months, in `unit`")
    high: int
    case_label: str = Field(description="The low and high case in words")
    risk: str
    params: dict[str, int | str] = Field(description="What Modify prefills")
    status: str = Field(
        description="pending | approved | auto_approved | declined | modified | lapsed"
    )
    outcome: str | None = Field(description="hit | miss | too_early once scored")
    measured_label: str | None = Field(description="What it reached, in words, once scored")


class PitchPolicyOut(BaseModel):
    """The player's pitch settings (27.1): the Holiday spend limit and the big-pitch stop."""

    auto_approve_cents: int | None = Field(description="Null: the default share of cash")
    default_cents: int = Field(description="What the default is now (5% of cash)")
    limit_cents: int = Field(description="The limit in force now")
    stop_for_big: bool


class PitchPolicyIn(BaseModel):
    auto_approve_cents: int | None = Field(
        default=None, ge=0, description="Null: 5% of cash; 0: always ask"
    )
    stop_for_big: bool = False


class ProposalOut(BaseModel):
    """An executive's proposal (24.1, M10c): pending ones block Continue."""

    proposal_id: int
    seat: str
    person_id: int
    name: str
    date_label: str
    kind: str = Field(description="round | loan | lease")
    text: str
    status: str = Field(description="pending | approved | declined | lapsed")


class DecisionOut(BaseModel):
    """Something an executive with authority did this month or lately (24.1-24.2)."""

    seat: str
    name: str
    date_label: str
    text: str
    mistake: bool = Field(description="A plausible but worse choice (24.2)")


class ReportOut(BaseModel):
    """A seat holder's latest quarterly report (24.3), as the inbox shows it."""

    seat: str
    person_id: int
    name: str
    date_label: str
    text: str


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
    proposals: list[ProposalOut] = Field(description="Pending first, then the latest (M10c)")
    decisions: list[DecisionOut] = Field(
        description="Executives' decisions of the last 3 months, newest first (M10c)"
    )
    reports: list[ReportOut] = Field(description="Each seat's latest quarterly report (M10c, 24.3)")
    pitches: list[PitchOut] = Field(
        default_factory=list, description="Pending first, then the latest (M13b, 27.1)"
    )
    pitch_policy: PitchPolicyOut | None = None


class ScaleupActionOut(BaseModel):
    scaleup: ScaleupOut
    energy: EnergyOut
    unread_inbox: int


class SharedServicesIn(BaseModel):
    services: str = Field(description="central | embedded")


class ProductDivisionIn(BaseModel):
    division_id: int | None = Field(description="Null makes the product corporate")


class AuthorityIn(BaseModel):
    """Give, change or withdraw a seat's authority (24.1); guardrails left out keep their
    current or default values."""

    enabled: bool
    guardrails: dict[str, float | list[int] | list[str]] = Field(default_factory=dict)


class AppointIn(BaseModel):
    person_id: int
    salary_cents: int | None = Field(
        default=None,
        description="New annual salary; null: the exec market rate, never below current pay",
    )


class AppointCandidateOut(BaseModel):
    person_id: int
    name: str
    role: str
    level: str
    fit: str
    estimated_effect_pct: float
    problem: str | None = Field(description="Why they cannot take the seat now, or null")
    salary_cents: int = Field(description="Their annual salary now")
    exec_salary_cents: int = Field(
        description="The default salary on appointment: the exec market rate, never below "
        "their current pay (18.3)"
    )


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
