"""The Government API (M44, docs/formulas.md 57.7): tenders once announced, their requirements,
the player's bids with score bands, awards and protests as published, the player's contracts and
their performance, clearance statuses, governments' budgets to this year, and rivals' published
awards. Never a rival's bid, an award or clearance draw, a pending clearance's decision month, a
protest's outcome before it is decided, or a budget or tender before it is announced."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class ScoreBandOut(BaseModel):
    total: str = Field(description="The bid's score band, e.g. '60-70' (never the score)")
    price: str
    technical: str
    past_performance: str


class MyBidOut(BaseModel):
    id: int
    tender_id: int
    product_id: int
    product: str
    price_cents: int
    team: list[int]
    month: str
    status: str = Field(description="submitted, won, lost, disqualified or withdrawn")
    band: ScoreBandOut | None = Field(
        description="Score bands once awarded (not when disqualified)"
    )
    reasons: list[str] = Field(description="Requirements the bid did not meet")
    can_protest: bool


class OptionOut(BaseModel):
    product_id: int
    product: str
    quality: float
    unmet: list[str] = Field(description="Requirements this product would not meet now")


class TenderOut(BaseModel):
    id: int
    title: str
    government: str
    government_label: str
    area: str
    buyer: str = Field(description="defence or civil")
    contract: str = Field(description="fixed_price, cost_plus or idiq")
    clearance: str = Field(description="none, secret or top_secret")
    value_cents: int = Field(description="The ceiling over the whole term (game scale)")
    term_months: int
    base_months: int
    awards: int = Field(description="Awardees (an IDIQ vehicle may have several)")
    large: bool
    announced: str
    closes: str
    award_month: str
    status: str = Field(description="open, evaluating, protested, awarded or cancelled")
    historical: bool = Field(description="A named tender from history (JEDI, JWCC, NSSL, ...)")
    winners: list[str] = Field(description="Published awardees, once awarded")
    winning_band: str | None = Field(description="The lowest awardee's score band, once awarded")
    protest_by: str | None = Field(description="Who protested the award, while it is held")
    requirements: list[str] = Field(description="What a bid must meet")
    options: list[OptionOut] = Field(description="The player's live products that could bid")
    my_bid: MyBidOut | None


class ContractOut(BaseModel):
    id: int
    tender_id: int
    title: str
    government_label: str
    area: str
    buyer: str
    contract: str
    product: str
    value_cents: int
    start: str
    base_end: str
    end: str
    status: str = Field(description="active, completed, terminated or defaulted")
    options: str = Field(description="pending, exercised or declined")
    performance: float = Field(description="0-100, the running mean of months delivered")
    revenue_cents: int
    cost_cents: int
    month_revenue_cents: int | None
    month_cost_cents: int | None


class ClearanceOut(BaseModel):
    person_id: int
    name: str
    level: str
    status: str = Field(description="pending, cleared, denied or lapsed")
    requested: str
    decided: str | None = Field(description="Shown once decided (never the month it is due)")


class FacilityClearanceOut(BaseModel):
    facility_id: int
    name: str
    status: str
    requested: str


class StaffOptionOut(BaseModel):
    person_id: int
    name: str
    role: str
    clearance: str | None = Field(description="The level held or pending, if any")


class FacilityOptionOut(BaseModel):
    facility_id: int
    name: str
    kind: str


class GovernmentOut(BaseModel):
    key: str
    label: str
    country: str
    defence_cents_year: int = Field(description="This year's defence budget, real 2010 cents")
    civil_cents_year: int = Field(description="This year's civil technology budget, real")
    open_to: list[str]
    refuses: list[str]
    open_tenders: int
    you_may_bid: bool = Field(description="Its tenders take bids from your bloc")


class RivalAwardOut(BaseModel):
    name: str
    awards: int
    value_cents: int = Field(description="Published awards' value over the last 36 months")
    areas: list[str]


class DefenceRecordOut(BaseModel):
    awards: int
    blocs: list[str] = Field(description="Blocs whose militaries the company supplies")
    brand_lost: float
    reactions: int = Field(description="Staff open letters so far")
    controlled_products: list[str] = Field(description="Products that are controlled items")
    past_performance: float = Field(description="The company's own record, 0-100")


class GovernmentScreenOut(BaseModel):
    month: str
    enabled: bool
    governments: list[GovernmentOut]
    tenders: list[TenderOut]
    contracts: list[ContractOut]
    clearances: list[ClearanceOut]
    facility_clearances: list[FacilityClearanceOut]
    staff: list[StaffOptionOut]
    facilities: list[FacilityOptionOut]
    rivals: list[RivalAwardOut]
    record: DefenceRecordOut
    clearance_cost_cents: dict[str, int] = Field(description="An investigation's price by level")
    facility_cost_cents: int
    protest_cost_cents: int


class BidIn(BaseModel):
    product_id: int
    price_cents: int = Field(gt=0)
    team: list[int] = Field(default_factory=list)


class ClearanceIn(BaseModel):
    person_ids: list[int]
    level: str = Field(description="secret or top_secret")


class GovernmentActionOut(BaseModel):
    government: GovernmentScreenOut
    energy: EnergyOut
    unread_inbox: int
