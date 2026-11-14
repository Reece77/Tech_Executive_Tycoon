"""The family (M36, formulas.md 45.9): members' public facts (names, ages, relations,
education, roles), their ratings as revealed ranges, readiness bands with their displayed
parts, closeness and the relationship, the adviser's opinions, estate-tax rules and quotes,
and the dynasty score with its parts. Never a family member's potential or hidden traits as
true values, or the draws behind life events."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.dynasty import DynastyOut
from tst.api.schemas.people import AttributeOut, EnergyOut


class FamilyIn(BaseModel):
    """The new game's Family setting (45.1)."""

    setting: str = Field(default="none", description="none | partner | children")
    child_ages: list[int] = Field(default_factory=list, description="'children': each one's age")


class EducationChoiceOut(BaseModel):
    stage: str = Field(description="school | university | mba")
    tier: str
    cost_cents: int


class ReadinessOut(BaseModel):
    band: str = Field(description="not_ready | developing | ready | strong")
    points: float = Field(description="From displayed values only")
    fit: float = Field(description="The CEO-seat score from displayed ranges (25.6's weights)")
    years: float
    seats: int
    board: float = Field(description="(board confidence - 50) / divisor")


class FamilyMemberOut(BaseModel):
    person_id: int
    name: str
    relation: str = Field(description="partner | child | ex_partner")
    age: int
    closeness: float | None = Field(description="A child's closeness, 0-100")
    school: str | None
    university: str | None
    degree: str | None
    mba: bool
    company_id: int | None
    company_name: str | None
    role: str | None
    level: str | None
    mentored: bool
    own_way: str | None
    interests: list[str]
    skills: list[AttributeOut]
    personality: list[AttributeOut]
    potential: str = Field(description="The potential phrase from the revealed range (as people)")
    readiness: ReadinessOut | None
    choices: list[EducationChoiceOut] = Field(description="Education open to choose now")
    can_join: bool


class OpinionOut(BaseModel):
    turn: int
    date_label: str
    subject: str
    subject_id: int
    title: str
    stance: str
    text: str
    overruled: bool


class AdviserOut(BaseModel):
    person_id: int
    name: str
    age: int
    retires_at: int
    opinions: list[OpinionOut]


class EstateOut(BaseModel):
    region: str
    rate: float
    exemption_cents: int
    used_exemption_cents: int
    shares: int
    share_price_cents: int
    shares_cents: int
    cash_cents: int
    other_cents: int
    estate_cents: int
    taxable_cents: int
    tax_cents: int
    shares_to_sell: int
    family_bp_now: int
    family_bp_after: int
    control_bp: int
    trust_shares: int
    gift_tax: bool
    lifetime_gifts_cents: int
    gift_tax_paid_cents: int
    estate_tax_paid_cents: int


class NoteOut(BaseModel):
    turn: int
    date_label: str
    kind: str
    text: str


class FamilyOut(BaseModel):
    exists: bool = Field(description="False when Family was set to none")
    setting: str
    head_id: int | None
    head_name: str | None
    head_mode: str = Field(description="founder | family_head (a professional CEO runs it)")
    family_time: int
    max_time: int
    time_now: int = Field(description="This month's family time (at least 15 under a promise)")
    energy_cost: int = Field(description="Family time plus mentoring, taken from the budget")
    relationship: float | None
    married: bool
    partner: FamilyMemberOut | None
    children: list[FamilyMemberOut]
    others: list[FamilyMemberOut] = Field(description="Ex-partners and the head's siblings")
    heirs: list[int] = Field(description="Children who can succeed now, readiest first")
    succession_open: str | None
    step_back_open: bool
    adviser: AdviserOut | None
    estate: EstateOut | None
    dynasty: DynastyOut | None
    notes: list[NoteOut]
    trust_since: str | None


class FamilyActionOut(BaseModel):
    family: FamilyOut
    energy: EnergyOut
    unread_inbox: int


class FamilyTimeIn(BaseModel):
    energy: int = Field(ge=0)


class EducateIn(BaseModel):
    person_id: int
    stage: str
    tier: str
    degree: str | None = None


class MentorIn(BaseModel):
    person_id: int
    on: bool


class FamilyJobIn(BaseModel):
    person_id: int
    company_id: int
    role: str
    level: str


class SuccessionIn(BaseModel):
    heir_id: int | None = None
    ceo_person_id: int | None = None
    professional: bool = False


class GiftIn(BaseModel):
    heir_id: int
    shares: int = Field(gt=0)


class SharesIn(BaseModel):
    shares: int = Field(gt=0)
