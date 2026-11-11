"""API schemas for breaking contracts (M23a)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class TerminationQuoteOut(BaseModel):
    contract: str
    contract_id: int
    company_id: int
    counterparty: str
    months_left: int
    monthly_minimum_cents: int = Field(description="A month's take-or-pay minimum")
    discounted_cents: int = Field(description="The months' minimums discounted at the base rate")
    penalty_cents: int
    prepaid_cents: int = Field(description="An offtake's unused prepayment kept against the fee")
    fee_cents: int
    cash_cents: int = Field(description="What leaves cash (negative: a refund)")
    relationship: float = Field(description="The counterparty's willingness to deal now, 0-1")
    energy: int


class TerminateIn(BaseModel):
    contract: str = Field(description="commodity, refining, production, mine or foundry")
    contract_id: int


class ContractActionOut(BaseModel):
    energy: EnergyOut
    unread_inbox: int
