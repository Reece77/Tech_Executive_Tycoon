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
    group: str  # technical | business | leadership | personality
    range: RangeOut


class TagOut(BaseModel):
    key: str
    label: str
    text: str  # e.g. "is a natural mentor"
    noticed_turn: int


class MoralePointOut(BaseModel):
    turn: int
    date_label: str
    morale: float


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


class PendingOfferOut(BaseModel):
    offer_id: int
    salary_cents: int
    equity_bp: int
    made_turn: int


class CandidacyOut(BaseModel):
    search_id: int
    channel: str
    expires_turn: int
    salary_expectation_cents: int
    pending_offer: PendingOfferOut | None


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
    employment: EmploymentOut | None
    candidacy: CandidacyOut | None
    noticed_tags: list[TagOut]


class PersonProfileOut(PersonSummaryOut):
    personality: list[AttributeOut]
    interests: list[str] | None = Field(description="Null until an interview or network intro")
    work_style: str | None = Field(description="Null until an interview or network intro")
    morale_history: list[MoralePointOut] = Field(description="Last 12 months, oldest first")


class SearchIn(BaseModel):
    role: str
    channel: str  # network | job_post | recruiter


class SearchOut(BaseModel):
    search_id: int
    role: str
    role_label: str
    channel: str
    opened_turn: int
    status: str
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


class EnergyOut(BaseModel):
    energy: int
    max: int


class ActionOut(BaseModel):
    energy: EnergyOut
    unread_inbox: int


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
    items: list[InboxItemOut]
