"""People, recruitment and inbox schemas (M1b). Never carry true values (ADR-0007).

Attributes are `{min, max}` ranges for the viewing company; potential is only a phrase;
current ability never appears.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RangeOut(BaseModel):
    min: int
    max: int


class AttributeOut(BaseModel):
    key: str
    label: str
    short_label: str  # for narrow columns; equals label for personality
    group: str  # technical | business | leadership | personality
    range: RangeOut


class TagOut(BaseModel):
    key: str
    label: str
    text: str  # e.g. "is a natural mentor"
    noticed_turn: int
    noticed_date_label: str


class MoralePointOut(BaseModel):
    turn: int
    date_label: str
    morale: float


class OptionsOut(BaseModel):
    """An employee's option grant for the contract panel (M4b, formulas.md 14.2)."""

    granted: int
    vested: int
    unvested: int
    fraction: float = Field(description="Options held over fully diluted shares")
    next_vest_label: str | None = Field(description="Month end that next vests; null when done")
    next_vest_shares: int
    next_vest_is_cliff: bool


class EmploymentOut(BaseModel):
    employment_id: int
    role: str
    role_label: str
    level: str
    salary_cents: int
    equity_bp: int
    start_turn: int
    status: str  # active | notice
    end_turn: int | None
    severance_cents: int  # what firing would cost now
    start_date_label: str
    end_date_label: str | None
    tenure_months: int
    market_rate_cents: int | None = Field(description="Role and level band mid for the region")
    monthly_cost_cents: int = Field(description="Salary, benefits and office per month")
    options: OptionsOut | None = Field(default=None, description="Null without a grant")


class PendingOfferOut(BaseModel):
    offer_id: int
    salary_cents: int
    equity_bp: int
    made_turn: int
    answer_date_label: str = Field(description="The month whose Continue resolves the offer")


class CandidacyOut(BaseModel):
    search_id: int
    channel: str
    expires_turn: int
    expires_date_label: str
    salary_expectation_cents: int
    pending_offer: PendingOfferOut | None
    offer_blocked_reason: str | None = Field(
        description='Why an offer is not allowed yet: null or "interview_required" (ADR-0016)'
    )


class KnowledgeOut(BaseModel):
    """How the viewing company has come to know someone (not what it knows)."""

    channel: str | None = Field(description="Search channel of an open candidacy")
    interviews: int
    reference_checks: int
    first_interview_date_label: str | None
    profile_known: bool = Field(description="Interests and work style are visible")


class PersonOrgOut(BaseModel):
    """Where a staff member sits in the org (M2b)."""

    unit_id: int | None = Field(description="Null for the company root")
    unit_name: str
    parent_unit_name: str | None = Field(description="The unit's parent unit, if any")
    manager_id: int | None = Field(description="Null for the founder")
    manager_name: str | None
    leads_unit_id: int | None = Field(description="The unit they lead, if any")


class PersonSummaryOut(BaseModel):
    person_id: int
    name: str
    age: int
    region: str
    role: str | None
    role_label: str | None
    level: str | None
    is_founder: bool
    morale: float | None
    potential_phrase: str
    skills: list[AttributeOut]
    personality: list[AttributeOut] = Field(
        description="Personality ranges (in the summary from M4c, for the candidate table)"
    )
    employment: EmploymentOut | None
    candidacy: CandidacyOut | None
    noticed_tags: list[TagOut]
    knowledge: KnowledgeOut
    interests: list[str] | None = Field(description="Null until an interview or network intro")
    org: PersonOrgOut | None = Field(default=None, description="Staff only (M2b)")
    energy: int | None = Field(
        default=None, description="Energy left this month: the founder and delegates only"
    )


class PersonProfileOut(PersonSummaryOut):
    work_style: str | None = Field(description="Null until an interview or network intro")
    work_style_matches_role: bool | None = Field(description="Null while work style is unknown")
    morale_history: list[MoralePointOut] = Field(description="Last 12 months, oldest first")


class RangeChangeOut(BaseModel):
    """One displayed range an action narrowed (M4c): what the viewer saw before and after."""

    key: str
    label: str
    group: str  # technical | business | leadership | personality
    before: RangeOut
    after: RangeOut


class LearnedOut(BaseModel):
    """What one interview, reference check or scout taught about a person (M4c). Built from
    displayed ranges before and after the action, never from true values (ADR-0007)."""

    person_id: int
    name: str
    action: str = Field(description="interview | reference_check | scout")
    ranges: list[RangeChangeOut] = Field(description="Ranges that narrowed, skills first")
    potential_before: str
    potential_after: str
    interests: list[str] | None = Field(description="Set when this action revealed them")
    work_style: str | None = Field(description="Set when this action revealed it")
    tags: list[TagOut] = Field(description="Behavior tags this action noticed")


class CheckOut(PersonProfileOut):
    """An interview or reference check: the candidate's profile now, and what it taught."""

    learned: LearnedOut


class SearchIn(BaseModel):
    role: str
    channel: str  # network | job_post | recruiter


class SearchOut(BaseModel):
    search_id: int
    role: str
    role_label: str
    channel: str
    opened_turn: int
    opened_date_label: str
    status: str
    closed_date_label: str | None
    next_batch_date_label: str | None = Field(description="When an open search's batch arrives")
    monthly_cost_cents: int
    open_candidates: int


class OfferIn(BaseModel):
    salary_cents: int = Field(gt=0)
    equity_bp: int = Field(default=0, ge=0)


class OfferOut(BaseModel):
    offer_id: int
    candidate_id: int
    salary_cents: int
    equity_bp: int
    made_turn: int
    status: str


class OfferPreviewOut(BaseModel):
    hint: str  # likely | uncertain | unlikely
    ratio: float  # offered salary / expectation
    floor_cents: int  # lowest salary that is not an automatic decline
    expectation_cents: int
    problems: list[str]  # rules the offer would break (option pool, per-offer cap)
    option_pool_left_bp: int
    options: int = Field(description="The offer's equity as options at today's FD (14.2)")
    fraction: float = Field(description="Those options over fully diluted shares")
    options_left: int = Field(description="Unallocated pool less other pending offers")
    fd_shares: int
    reasons: list[str] = Field(description="Why the hint reads as it does, from known values only")


class EnergyOut(BaseModel):
    energy: int
    max: int


class ActionOut(BaseModel):
    energy: EnergyOut
    unread_inbox: int


class ScoutOut(ActionOut):
    learned: list[LearnedOut] = Field(description="What the scouting taught, per candidate")


class FireOut(ActionOut):
    severance_cents: int


class InboxItemOut(BaseModel):
    item_id: int
    turn: int
    date_label: str
    kind: str
    title: str
    body: str
    link_kind: str | None
    link_id: int | None
    read: bool


class InboxOut(BaseModel):
    unread: int
    total: int = Field(description="Messages matching the query, before paging (M2b)")
    offset: int = 0
    items: list[InboxItemOut]
