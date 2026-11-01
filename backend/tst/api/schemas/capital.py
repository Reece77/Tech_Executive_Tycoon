"""Debt and macro schemas (M10, docs/formulas.md 20.4).

What the API may show: the macro indicators for months already played (history while the
calendar is inside it) and "downturn under way"; never a future month or the AR(1) draws.
Loans with balance, rate, the schedule at today's balance and rate, and covenant headroom.
Rates travel as basis points a year; money as integer cents.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MacroMonthOut(BaseModel):
    turn: int
    label: str = Field(description="e.g. 'Jun 2022'")
    base_rate: float = Field(description="% a year")
    climate: float = Field(description="Venture climate multiplier")
    confidence: float = Field(description="Consumer confidence, 100 = the 2010-2019 average")
    ai_index: float = Field(description="AI compute cost against 2010 (1.0)")


class MacroIndicatorOut(BaseModel):
    key: str = Field(description="base_rate, climate, confidence or ai_index")
    label: str
    value: float
    display: str = Field(description="The value as shown, e.g. '4.33%' or 'x 0.90'")
    context: str = Field(description="One line of context")


class MacroOut(BaseModel):
    current: MacroMonthOut = Field(description="The month the player is in")
    indicators: list[MacroIndicatorOut]
    months: list[MacroMonthOut] = Field(description="The last 24 months and this one, oldest first")
    adoption_factor: float = Field(description="Consumer and SMB adoption x this (20.1)")
    downturn: bool = Field(description="A downturn is under way")
    history_ends_label: str = Field(description="The last month of real history")
    after_history: bool = Field(description="The calendar has passed the real history")


class CovenantOut(BaseModel):
    description: str
    measure_cents: int
    required_cents: int
    headroom_cents: int
    holds: bool


class PaymentOut(BaseModel):
    turn: int
    label: str
    interest_cents: int
    principal_cents: int
    balance_after_cents: int


class LoanOut(BaseModel):
    id: int
    instrument: str = Field(description="venture_debt or bank_loan")
    instrument_label: str
    lender: str
    principal_cents: int
    signed_turn: int
    signed_label: str
    warrant_shares: int
    balance_cents: int
    rate_bp: int = Field(description="Basis points a year")
    status: str = Field(description="active, repaid or called")
    status_label: str
    term_months: int
    interest_only_months: int
    ends_label: str
    interest_paid_cents: int
    principal_paid_cents: int
    next_payment: PaymentOut | None = Field(description="This month's payment at Continue")
    covenants: list[CovenantOut] = Field(description="Tested at today's cash and history")
    covenants_resting_until_label: str | None = Field(
        description="After a breach covenants are not tested until this month"
    )
    breaches: int
    schedule: list[PaymentOut] = Field(description="From this month to the end of the term")


class LoanTermsOut(BaseModel):
    instrument: str
    instrument_label: str
    eligible: bool
    problem: str | None = Field(description="Why it is not offered now, in words")
    lender: str | None
    rate_bp: int
    term_months: int
    interest_only_months: int
    max_cents: int
    min_cents: int
    warrant_bp: int = Field(description="Of fully diluted shares, after they are issued")
    covenant: str = Field(description="The covenant in words")
    breach: str = Field(description="What a breach brings, in words")
    energy: int


class LoansOut(BaseModel):
    loans: list[LoanOut]
    offers: list[LoanTermsOut]
    debt_cents: int = Field(description="Principal owed on every active loan")
    repay_energy: int


class LoanIn(BaseModel):
    instrument: str
    amount_cents: int


class LoanPreviewOut(BaseModel):
    problem: str | None
    first_payment: PaymentOut | None
    rate_bp: int
    warrant_shares: int


class RepayIn(BaseModel):
    amount_cents: int | None = Field(default=None, description="Null repays the whole balance")
