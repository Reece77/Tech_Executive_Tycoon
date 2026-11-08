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
