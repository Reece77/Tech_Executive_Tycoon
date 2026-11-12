"""Group screen schemas (M16, formulas.md 31.10): the entity tree with stakes and treatments,
each company's public numbers, and the holding company's gate. Never a minority investor's or
a board's hidden thresholds, nor a private company's true value (a range, 28.1)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class GroupEntityOut(BaseModel):
    company_id: int
    name: str
    parent_id: int | None = Field(description="Its direct owner inside the group; null: the root")
    depth: int = Field(description="0 for the root, 1 for its subsidiaries, ...")
    role: str = Field(description="holding | operating | subsidiary | company")
    stake_bp: int = Field(description="The group's stake held by its direct owner, basis points")
    treatment: str = Field(description="root | consolidated | equity | fair_value (31.3)")
    listed: bool
    revenue_cents: int = Field(description="Revenue over the last 12 month ends")
    operating_margin: float | None = Field(
        description="Operating result over revenue for the last 12 month ends; null without revenue"
    )
    cash_cents: int
    market_cap_cents: int | None = Field(default=None, description="Listed companies only")
    value_low_cents: int | None = Field(default=None, description="Private: the value range (28.1)")
    value_high_cents: int | None = None
    ceo: str | None = Field(default=None, description="Its CEO's name (subsidiaries)")
    mandate: str | None = Field(default=None, description="grow | margin | return_cash (31.4)")
    capex_limit_cents: int = 0
    review: str = Field(default="", description="The last December review's result")
    misses: int = 0
    replacement_proposed: bool = False
    board_seats: list[int] = Field(
        default_factory=list, description="[parent nominees, independents, minority seats]"
    )


class GroupPitchOut(BaseModel):
    id: int
    company_id: int
    company: str
    ceo: str
    turn: int
    amount_cents: int
    fits_mandate: bool
    status: str


class StakeOut(BaseModel):
    company_id: int
    company: str
    stake_bp: int
    treatment: str = Field(description="equity | fair_value (31.3)")
    kind: str = Field(description="market | venture | retained")
    carrying_cents: int
    cost_cents: int


class PersonalStakeOut(BaseModel):
    company_id: int
    company: str
    stake_bp: int


class FlowOut(BaseModel):
    id: int
    seller_id: int
    seller: str
    buyer_id: int
    buyer: str
    good: str = Field(description="compute | chips")
    price_kind: str = Field(description="cost | cost_plus | market")
    margin: float | None
    last_price_cents: int = Field(description="The transfer price paid at the last month end")
    unfair_months: int = Field(description="Months running more than 10% from market")
    minorities: bool = Field(description="A company of the flow has outside shareholders")
    complaint: bool


class DiscountOut(BaseModel):
    """From public numbers only (31.10): listed parts at market, private ones at their
    displayed range's midpoint."""

    parts_cents: int = Field(description="The sum of the parts (31.7)")
    segments: int
    intra_share: float = Field(description="Intra-group revenue over the year's group revenue")
    discount: float = Field(description="The conglomerate discount d, 0.10-0.25")
    after_discount_cents: int = Field(description="The sum of the parts x (1 - d)")


class GroupOut(BaseModel):
    formed: bool
    holding_id: int | None
    can_form: bool
    reasons: list[str] = Field(description="What still stands in the way of forming one (31.2)")
    form_energy: int
    form_fee_cents: int = Field(description="0.1% of the market cap at the last month end")
    office_monthly_cents: int
    entities: list[GroupEntityOut] = Field(description="Owners before what they own")
    pitches: list[GroupPitchOut] = Field(default_factory=list, description="Pending requests")
    stakes: list[StakeOut] = Field(default_factory=list, description="Stakes it does not control")
    personal_stakes: list[PersonalStakeOut] = Field(
        default_factory=list, description="The founder's own shares in spun-off companies"
    )
    flows: list[FlowOut] = Field(default_factory=list, description="Intra-group supply (31.6)")
    discount: DiscountOut | None = Field(
        default=None, description="The listed holding company's conglomerate discount (31.7)"
    )
    mandate_energy: int = 0


class MandateIn(BaseModel):
    company_id: int
    mandate: str = Field(description="grow | margin | return_cash")
    capex_limit_cents: int = Field(default=0, ge=0, description="0: no limit")
    categories: list[str] = Field(default_factory=list, description="Empty: any")
    regions: list[str] = Field(default_factory=list, description="Empty: any")


class PitchAnswerIn(BaseModel):
    approve: bool


class GroupActionOut(BaseModel):
    group: GroupOut
    energy: EnergyOut
    unread_inbox: int


class StakeIn(BaseModel):
    company_id: int
    stake_bp: int = Field(description="Share of the company, basis points")


class SpinOffIn(BaseModel):
    company_id: int
    keep_bp: int = Field(default=0, ge=0, description="What the group keeps, at most 19.9%")


class VentureIn(BaseModel):
    company_id: int
    cents: int = Field(gt=0)


class TransferPriceIn(BaseModel):
    seller_id: int
    buyer_id: int
    good: str = Field(description="compute | chips")
    price_kind: str = Field(description="cost | cost_plus | market")
    margin: float | None = Field(default=None, description="cost plus: the margin, 0-1")


# --- M23c: the capital-actions history and subsidiaries' quarterly updates ----------------


class CapitalActionOut(BaseModel):
    turn: int
    date_label: str
    kind: str = Field(description="stake_sale | carve_out | spin_off | buyout")
    kind_label: str
    company_id: int
    company: str
    owner: str = Field(description="The group company that sold or bought")
    proceeds_cents: int = Field(description="Cash in (a buyout's price is negative)")
    stake_before_bp: int
    stake_after_bp: int
    nci_cents: int = Field(description="Non-controlling interest left: minorities' book equity")
    value_created_cents: int = Field(
        description="The equity effect on the owner's books: what the sale fetched over the "
        "book value given up (a buyout: below the minority's book; negative is a premium paid)"
    )
    value_note: str
    market_cap_now_cents: int | None = Field(description="Its market cap now, when listed")
    stake_value_now_cents: int | None = Field(description="What the group's stake is worth now")


class CapitalHistoryOut(BaseModel):
    actions: list[CapitalActionOut]


class AdviceOut(BaseModel):
    mandate: str = Field(description="grow | margin | return_cash")
    label: str
    current: bool


class SubsidiaryUpdateOut(BaseModel):
    company_id: int
    company: str
    ceo: str
    quarter_label: str
    revenue_cents: int = Field(description="The latest quarter's revenue")
    prior_revenue_cents: int = Field(description="The quarter before")
    operating_margin: float | None
    cash_cents: int
    mandate: str | None
    capex_limit_cents: int
    categories: list[str]
    regions: list[str]
    body: str = Field(description="The CEO's update in their own words, from public numbers")
    question: str = Field(description="What the CEO asks the Chair")
    advice: list[AdviceOut] = Field(description="Answers: each re-sets the mandate (31.4)")
    advice_energy: int = Field(description="Founder energy an answer takes (a mandate change)")


class SubsidiaryUpdatesOut(BaseModel):
    updates: list[SubsidiaryUpdateOut]
