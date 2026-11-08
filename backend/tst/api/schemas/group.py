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


class GroupOut(BaseModel):
    formed: bool
    holding_id: int | None
    can_form: bool
    reasons: list[str] = Field(description="What still stands in the way of forming one (31.2)")
    form_energy: int
    form_fee_cents: int = Field(description="0.1% of the market cap at the last month end")
    office_monthly_cents: int
    entities: list[GroupEntityOut] = Field(description="Owners before what they own")


class GroupActionOut(BaseModel):
    group: GroupOut
    energy: EnergyOut
    unread_inbox: int
