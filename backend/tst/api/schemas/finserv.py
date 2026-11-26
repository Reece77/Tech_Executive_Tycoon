"""The Bank, Payments, Insurance and Currency screens (M54, docs/formulas.md 64). Public figures
only (64.5): a bank's run risk is a band, never its chance; a stress test shows only once it has
run; a catastrophe only once it has happened; currency indexes only to this month."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class FinRegionOptionOut(BaseModel):
    region: str
    label: str
    regulator: str
    months: int = Field(description="Months to a charter or licence there")
    strict: bool = Field(description="A strict regulator (adds months to a charter)")


class BankLoanOut(BaseModel):
    kind: str
    label: str
    balance_cents: int
    risk_weight: float
    yield_rate: float = Field(description="% a year: the policy rate plus the kind's spread")
    loss_rate: float = Field(description="% a year charged off this year")


class BankStressOut(BaseModel):
    month: str
    ratio_after: float
    passed: bool


class BankRunOut(BaseModel):
    month: str
    withdrawn_cents: int
    realised_loss_cents: int
    failed: bool


class BankMonthOut(BaseModel):
    month: str
    deposits_cents: int
    loans_cents: int
    nii_cents: int = Field(description="Net interest income this month")
    profit_cents: int = Field(description="Net interest income less charge-offs")
    nim: float = Field(description="Net interest margin, a year, of earning assets")
    ratio: float = Field(description="CET1 / risk-weighted assets")
    policy_rate: float
    deposit_rate: float


class OwnBankOut(BaseModel):
    id: int
    region: str
    label: str
    status: str = Field(description="applying, chartered, partner or failed")
    regulator: str
    charter_month: str | None = Field(description="When the regulator decides (applying)")
    beta: float
    loan_to_deposit: float
    securities_share: float
    duration: float
    deposits_cents: int
    consumer_deposits_cents: int
    business_deposits_cents: int
    loans_cents: int
    loans: list[BankLoanOut]
    securities_cents: int
    securities_value_cents: int = Field(description="Market value at today's rate")
    unrealised_loss_cents: int
    reserves_cents: int
    cet1_cents: int
    rwa_cents: int
    ratio: float | None = Field(description="CET1 / RWA (null without loans)")
    requirement: float = Field(description="Minimum plus buffers (and the size surcharge)")
    minimum: float
    nim: float | None = Field(description="The last 12 months' net interest margin")
    policy_rate: float
    deposit_rate: float
    market_deposit_rate: float
    uninsured_share: float
    insured_limit_cents: int
    run_risk: str = Field(description="low, elevated or high: a band, never the chance")
    restricted: bool
    dividends_frozen_until: str | None
    capital_in_cents: int
    stress: list[BankStressOut]
    runs: list[BankRunOut]
    months: list[BankMonthOut]


class BankScreenOut(BaseModel):
    can_charter: bool = Field(description="The company has a fintech or banking line")
    has_banking_line: bool
    charter_capital_cents: int
    charter_fee_cents: int
    beta_range: list[float]
    duration_range: list[float]
    reserve_min: float
    partner_share: float
    regions: list[FinRegionOptionOut]
    banks: list[OwnBankOut]
    charters: list[str] = Field(description="Fintechs that took charters (history)")


class NetworkOut(BaseModel):
    id: int
    region: str
    label: str
    since: str
    acceptance: float = Field(description="Share of merchants that take it")
    share: float = Field(description="Its share of the region's card programmes")
    volume_cents: int = Field(description="Card volume it carries this month")


class PaymentsRegionOut(BaseModel):
    region: str
    label: str
    acquired_cents: int = Field(description="Your merchants' card volume this month")
    revenue_cents: int = Field(description="Your payments lines' revenue there this month")
    take_rate: float | None = Field(description="Revenue over volume carried")
    interchange_cents: int
    fraud_cents: int
    interchange_bp: float
    rails_share: float = Field(description="Real-time rails' share of the region's volume")
    networks: dict[str, float] = Field(description="The listed networks' shares (history)")


class PaymentsScreenOut(BaseModel):
    can_launch: bool = Field(description="The company has a payments line")
    network_cost_cents: int
    network_fee_bp: float
    fraud_bp: float
    networks: list[NetworkOut]
    regions: list[PaymentsRegionOut]


class InsuranceLicenceOut(BaseModel):
    region: str
    label: str
    status: str
    decided: str | None


class LineMonthOut(BaseModel):
    month: str
    premiums_cents: int
    claims_cents: int
    combined_ratio: float
    investment_income_cents: int
    float_cents: int
    own_funds_cents: int
    required_cents: int
    catastrophe: bool


class CatastropheOut(BaseModel):
    month: str
    region: str
    label: str


class InsuranceScreenOut(BaseModel):
    can_apply: bool = Field(description="The company has an insurance line")
    licence_capital_cents: int
    licence_fee_cents: int
    regions: list[FinRegionOptionOut]
    has_insurer: bool
    licences: list[InsuranceLicenceOut]
    investments_cents: int
    float_cents: int
    own_funds_cents: int
    required_cents: int
    solvent: bool
    premiums_by_line: dict[str, int] = Field(description="This month's premiums by line")
    months: list[LineMonthOut]
    catastrophes: list[CatastropheOut] = Field(description="Those that have happened")


class HedgeOut(BaseModel):
    id: int
    region: str
    label: str
    notional_cents: int
    bought: str
    settles: str
    spot_index: float
    forward_index: float
    value_cents: int
    status: str
    settled_cents: int
    programme: bool


class CurrencyRegionOut(BaseModel):
    region: str
    label: str
    currency: str = Field(description="Its basket")
    index: float = Field(description="US dollars a unit now over January 2010's")
    change_12m: float | None
    policy_rate: float
    revenue_cents: int = Field(description="This month, translated")
    untranslated_revenue_cents: int = Field(description="At the indexes prices were set at")
    cost_cents: int
    net_cents: int
    exposure_cents: int = Field(description="The next 12 months' net revenue at today's index")
    hedged_cents: int = Field(description="Open forwards' notional")
    unhedged_share: float | None
    what_if_cents: int = Field(description="A year's net revenue change if the dollar rises")
    forward_12m_index: float | None
    spread_bp: int


class ProgrammeOut(BaseModel):
    share: float
    term_months: int
    by_cfo: bool


class CurrencyScreenOut(BaseModel):
    month: str
    what_if_move: float
    term_range: list[int]
    max_hedge_share: float
    foreign_share: float = Field(description="Foreign revenue over all revenue this month")
    regions: list[CurrencyRegionOut]
    hedges: list[HedgeOut]
    programme: ProgrammeOut | None
    fx_result_12m_cents: int = Field(description="Currency gains less losses, last 12 months")


class FinservScreenOut(BaseModel):
    month: str
    history: bool = Field(description="Before 2026: rivals follow the history")
    bank: BankScreenOut
    payments: PaymentsScreenOut
    insurance: InsuranceScreenOut
    currency: CurrencyScreenOut


class FinservActionOut(BaseModel):
    finserv: FinservScreenOut
    energy: EnergyOut
    unread_inbox: int


class RegionIn(BaseModel):
    region: str


class BankSettingsIn(BaseModel):
    beta: float
    loan_to_deposit: float
    securities_share: float
    duration: float


class AmountIn(BaseModel):
    amount_cents: int


class ForwardIn(BaseModel):
    region: str
    notional_cents: int = Field(gt=0)
    months: int


class ProgrammeIn(BaseModel):
    share: float = Field(ge=0, le=1)
    term_months: int = 12
