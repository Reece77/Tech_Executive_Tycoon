"""Response and request schemas for the IPO flow, the Stock tab and the CEO seat (M13,
docs/formulas.md 25.8).

Only what 25.8 allows: the IPO chain's status and choices; the price range, and the book as a
word, never its draw; the share price, its history and market cap; analysts' ratings and
targets; guidance against actuals; the founder's stake; the CEO's decisions and overrides.
Never V_f or its parts beyond what analysts publish, the sentiment behind the price, its
future, or the activist and takeover thresholds.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class BankOut(BaseModel):
    key: str
    name: str
    fee_pct: float = Field(description="Percent of the money raised")
    reputation: str = Field(description="How the bank's name helps the price, in words")


class IpoStepOut(BaseModel):
    key: str = Field(description="banks, filing, roadshow, pricing, listing")
    label: str
    state: str = Field(description="done, now or next")
    detail: str


class PriceOptionOut(BaseModel):
    choice: str = Field(description="range, raise, cut or pull")
    label: str
    price_cents: int = Field(description="A share; 0 for pull")
    gross_cents: int
    net_cents: int = Field(description="After the bank's fee; for pull, minus the fees owed")
    first_day: str = Field(description="The likely first day, in words (est.)")
    available: bool
    note: str


class IpoOut(BaseModel):
    status: str
    bank: str
    fee_pct: float
    hired: str = Field(description="Mon YYYY")
    steps: list[IpoStepOut]
    ambition: str | None
    share_sold_pct: float | None
    dual_class: bool | None
    demand: str | None = Field(description="The book in words (strong, weak...), from pricing")
    price_cents: int | None = Field(description="The bank's suggested price a share")
    new_shares: int
    shares_after: int
    implied_cap_cents: int
    price_to_sales: float | None
    stake_pct_after: float
    stake_value_cents: int
    options: list[PriceOptionOut]
    listed: str | None
    first_day_pct: float | None
    pulled: str | None


class SharePointOut(BaseModel):
    turn: int
    label: str
    price_cents: int
    market_cap_cents: int
    mark: str = Field(description="listing, beat, miss, inline or empty")


class AnalystOut(BaseModel):
    firm: str
    rating: str
    target_cents: int


class GuidanceRowOut(BaseModel):
    quarter: str = Field(description="Q1 2016")
    by_player: bool
    revenue_cents: int
    margin_pct: float
    actual_revenue_cents: int | None
    actual_margin_pct: float | None
    result: str | None
    price_before_cents: int | None
    price_after_cents: int | None


class NextGuidanceOut(BaseModel):
    quarter: str
    can_set: bool
    problem: str | None
    consensus_revenue_cents: int
    consensus_margin_pct: float
    set_revenue_cents: int | None
    set_margin_pct: float | None
    band_pct: float = Field(description="Guidance must lie within this % of the consensus")
    energy: int
    hint: str


class CapitalOut(BaseModel):
    buyback_price_cents: int
    buyback_max_shares: int
    buyback_energy: int
    dividend_declared_cents: int
    dividend_energy: int
    shares_outstanding: int
    secondary_price_cents: int
    secondary_max_shares: int
    secondary_fee_pct: float
    secondary_energy: int


class DriverOut(BaseModel):
    label: str
    effect: str = Field(description="Words only: lifts, weighs on, neutral")
    detail: str


class StockOut(BaseModel):
    ticker: str
    price_cents: int
    change_pct: float | None = Field(description="Since last month end")
    market_cap_cents: int
    shares: int
    listing_price_cents: int
    listed: str
    dual_class: bool
    stake_shares: int
    stake_pct: float
    stake_value_cents: int
    history: list[SharePointOut]
    analysts: list[AnalystOut]
    buys: int
    holds: int
    sells: int
    average_target_cents: int | None
    guidance: list[GuidanceRowOut]
    next_guidance: NextGuidanceOut
    capital: CapitalOut
    board_line: str
    drivers: list[DriverOut]


class CeoDecisionOut(BaseModel):
    id: int
    turn: int
    label: str
    scope: str
    text: str
    mistake: bool
    can_override: bool
    overridden: bool


class CeoCandidateOut(BaseModel):
    person_id: int
    name: str
    role: str
    level: str


class CeoOut(BaseModel):
    seat_open: bool = Field(description="Stage 4: the founder may appoint a CEO")
    problem: str | None
    person_id: int | None
    name: str | None
    since: str | None
    scopes: list[str]
    all_scopes: list[str]
    decisions: list[CeoDecisionOut]
    candidates: list[CeoCandidateOut]
    appoint_energy: int
    override_energy: int
    chair_energy: int


class PublicOut(BaseModel):
    stage: int
    eligible: bool
    problem: str | None = Field(description="Why the company cannot hire banks now")
    banks: list[BankOut]
    hire_energy: int
    ipo: IpoOut | None
    stock: StockOut | None
    ceo: CeoOut


class PublicActionOut(BaseModel):
    public: PublicOut
    energy: EnergyOut
    unread_inbox: int


class HireBanksIn(BaseModel):
    bank: str


class GuidanceIn(BaseModel):
    revenue_cents: int = Field(gt=0)
    margin_bp: int = Field(ge=-10_000, le=10_000)


class BuybackIn(BaseModel):
    amount_cents: int = Field(gt=0)


class DividendIn(BaseModel):
    per_share_cents: int = Field(gt=0)


class SecondaryIn(BaseModel):
    shares: int = Field(gt=0)


class AppointCeoIn(BaseModel):
    person_id: int


class CeoAuthorityIn(BaseModel):
    scopes: list[str]
