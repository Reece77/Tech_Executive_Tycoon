"""Response and request schemas for mergers and acquisitions (M14, formulas.md 28.8).

Only what 28.8 allows: listed companies' market caps; private companies' value ranges
(narrower after diligence); a target's revealed people and products as ranges after
diligence; offers, counters, review status and outcomes; subsidiaries; integration progress.
Never V_f's components for a private company, a reservation price, a board's bar, a tender's
chance, a review's block probability or a hidden problem before diligence or closing.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class TargetProductOut(BaseModel):
    product_id: int
    name: str
    category: str
    quality_low: int | None = Field(description="After diligence: quality as a range (28.2)")
    quality_high: int | None = None
    feature_low: int | None = Field(description="After diligence: the feature score as a range")
    feature_high: int | None = None


class TargetPersonOut(BaseModel):
    person_id: int
    name: str
    role: str


class TargetOut(BaseModel):
    company_id: int
    name: str
    kind: Literal["incumbent", "startup"]
    listed: bool
    market_cap_cents: int | None = Field(description="Listed: V_f x sentiment, public")
    value_low_cents: int | None = Field(description="Private: the estimated value range")
    value_high_cents: int | None = None
    categories: list[str]
    diligence: Literal["none", "under_way", "done"]
    diligence_cost_cents: int = Field(description="0.5% of the estimate, at least $50,000")
    findings: list[str] = Field(description="Hidden problems, only once diligence is done")
    products: list[TargetProductOut]
    people: list[TargetPersonOut] = Field(description="Key people, once diligence is done")
    counter_cents: int | None = Field(description="Their counter-offer, once they made one")
    talks_closed_months: int | None = Field(description="Months until a new bid is possible")
    open_deal_id: int | None
    integrate_allowed: bool = Field(description="At most integration.max_staff staff")
    integrate_note: str | None = Field(default=None, description="Why it must be a brand")


class DealOut(BaseModel):
    deal_id: int
    target_id: int
    target_name: str
    price_cents: int
    cash_share: float
    status: Literal["accepted", "review", "blocked", "refused", "closed", "abandoned", "failed"]
    hostile: bool
    mode: Literal["brand", "integrate"] | None
    made_turn: int
    close_turn: int | None = Field(description="Due to close at this turn's month end")
    review_end_turn: int | None
    combined_share: float = Field(description="The highest combined share antitrust saw")
    market: str
    remedy_product: str | None = Field(description="The product a remedy would divest")
    own_remedy_product: str | None = Field(
        default=None, description="Your own overlapping product, offered instead (M15b)"
    )


class AcquisitionOut(BaseModel):
    deal_id: int
    company_id: int
    name: str
    mode: Literal["brand", "integrate"]
    closed_turn: int
    price_cents: int
    directive: Literal["grow", "harvest", "defend"]
    key_people: int
    pool_kept: int
    let_go: int
    departed: int
    problems: list[str]
    clash_months_left: int
    cost_before_cents: int = Field(description="The target's monthly costs before closing")
    unit_ids: list[int] = Field(description="Your units created for its products")
    flagged: bool = Field(description="Org flags its units this long after closing")


class SubsidiaryOut(BaseModel):
    company_id: int
    name: str
    directive: Literal["grow", "harvest", "defend"]
    mrr_cents: int
    cash_cents: int
    staff: int


class MnaOut(BaseModel):
    targets: list[TargetOut]
    deals: list[DealOut]
    acquisitions: list[AcquisitionOut]
    subsidiaries: list[SubsidiaryOut]
    listed: bool = Field(description="Whether you can pay in shares")


class MessageOut(BaseModel):
    title: str
    detail: str


class MnaActionOut(BaseModel):
    mna: MnaOut
    energy: EnergyOut
    unread_inbox: int
    messages: list[MessageOut]


class DiligenceIn(BaseModel):
    company_id: int


class BidIn(BaseModel):
    company_id: int
    price_cents: int = Field(gt=0)
    cash_share: float = Field(default=1.0, ge=0, le=1)
    hostile: bool = False
    mode: Literal["brand", "integrate"] = "integrate"


class DealModeIn(BaseModel):
    mode: Literal["brand", "integrate"]


class DirectiveIn(BaseModel):
    directive: Literal["grow", "harvest", "defend"]
