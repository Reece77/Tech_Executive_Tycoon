"""The founder's own investments (M26, formulas.md 37.7): net worth and its parts with history,
angel stakes with their startups' funding history and cash band, open rounds, the network,
public holdings and trades with "sensitive window" flags, and the family office with its
manager's revealed skill range. Never a trade's regulatory risk, an investigation's chance or
timing, a concealed conflict's discovery, a manager's true skill or a startup's true value."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class NetWorthOut(BaseModel):
    total_cents: int
    cash_cents: int
    angel_cents: int = Field(description="Angel stakes at their startups' last round price")
    public_cents: int = Field(description="Listed shares at the share price")
    family_office_cents: int
    own_stake_cents: int = Field(
        description="Your stake in your own company: at market once listed, else 28.1's value"
    )


class NetWorthPointOut(BaseModel):
    turn: int
    date_label: str
    total_cents: int
    own_stake_cents: int


class StartupRoundOut(BaseModel):
    date_label: str
    raised_cents: int
    post_cents: int = Field(description="The round's price (post-money)")
    source: str = Field(description="founded | funded | venture | angel | backed")


class AngelStakeOut(BaseModel):
    id: int
    company_id: int
    company: str
    category_label: str
    status: Literal["open", "acquired", "listed", "failed"]
    stake_pct: float
    cost_cents: int
    worth_cents: int = Field(description="Stake x the last round's post-money")
    proceeds_cents: int
    backed: bool
    founder_known: bool = Field(description="Backed with a founder whose skills you knew")
    since_label: str
    closed_label: str | None
    cash_band: str | None = Field(description="deep pockets | comfortable | tight")
    funding: list[StartupRoundOut]
    conflict: str | None = Field(description="disclosed | concealed | found, once raised")


class OpenRoundOut(BaseModel):
    company_id: int
    company: str
    category_label: str
    date_label: str
    raised_cents: int
    post_cents: int
    max_cents: int = Field(description="The most your cheque can be: the round's size")
    held_pct: float = Field(description="Your stake now (0 if none)")


class NetworkPersonOut(BaseModel):
    person_id: int
    name: str
    role_label: str
    source: Literal["former", "candidate"]
    known: bool = Field(description="You know their skills well (narrow revealed ranges)")


class CategoryOptionOut(BaseModel):
    key: str
    label: str


class HoldingOut(BaseModel):
    company_id: int
    company: str
    shares: int
    price_cents: int | None
    worth_cents: int
    cost_cents: int
    own: bool = Field(description="Your own company (these shares sit on its cap table)")


class ListedOut(BaseModel):
    company_id: int
    company: str
    price_cents: int
    own: bool
    window_open: bool = Field(description="Own company: closed in the month before earnings")
    sensitive: bool = Field(description="A trade now would be in a sensitive window")


class TradeOut(BaseModel):
    id: int
    date_label: str
    company_id: int
    company: str
    side: Literal["buy", "sell"]
    shares: int
    price_cents: int
    filed: bool = Field(description="A public filing (an own-company sale above 1%)")
    sensitive: bool = Field(description="Made in a sensitive window")
    investigation: Literal["open", "finding"] | None = Field(
        description="Shown once an investigation has opened"
    )


class OfficeReturnOut(BaseModel):
    turn: int
    date_label: str
    return_pct: float


class FamilyOfficeOut(BaseModel):
    formed_label: str
    mandate: str
    balance_cents: int
    manager_id: int
    manager_name: str
    manager_skill_low: int = Field(description="The manager's finance skill, revealed range")
    manager_skill_high: int
    returns: list[OfficeReturnOut] = Field(description="The last 24 months, oldest first")
    trailing_year_pct: float | None
    index_year_pct: float | None = Field(description="The market index over the same year")


class FamilyOfficeFormOut(BaseModel):
    can_form: bool
    min_cents: int
    wealth_cents: int = Field(description="Cash plus investments at value, outside your company")
    energy: int
    move_energy: int
    mandates: list[str]


class IndexPointOut(BaseModel):
    turn: int
    date_label: str
    level: float


class InvestingRulesOut(BaseModel):
    join_energy: int
    back_energy: int
    trade_energy: int
    round_min_cents: int
    min_cheque_cents: int
    seed_stake_low_pct: float
    seed_stake_high_pct: float
    seed_full_cents: int
    trade_cost_pct: float


class InvestmentsOut(BaseModel):
    personal_cash_cents: int
    net_worth: NetWorthOut
    history: list[NetWorthPointOut] = Field(description="Month ends, oldest first")
    stakes: list[AngelStakeOut]
    open_rounds: list[OpenRoundOut]
    network: list[NetworkPersonOut]
    categories: list[CategoryOptionOut] = Field(description="Where a new startup can start")
    holdings: list[HoldingOut]
    listed: list[ListedOut]
    trades: list[TradeOut] = Field(description="Newest first")
    family_office: FamilyOfficeOut | None
    family_office_form: FamilyOfficeFormOut
    index: list[IndexPointOut] = Field(description="The market index, the last 60 months")
    rules: InvestingRulesOut


class InvestmentsActionOut(BaseModel):
    investments: InvestmentsOut
    energy: EnergyOut
    unread_inbox: int


class JoinRoundIn(BaseModel):
    company_id: int
    cents: int = Field(gt=0)


class BackStartupIn(BaseModel):
    founder_id: int
    category: str
    cents: int = Field(gt=0)


class TradeIn(BaseModel):
    company_id: int
    side: Literal["buy", "sell"]
    shares: int = Field(gt=0)


class OfficeMandateIn(BaseModel):
    mandate: Literal["conservative", "balanced", "aggressive"]


class MoveIn(BaseModel):
    cents: int = Field(description="Into the office if positive, out of it if negative")
