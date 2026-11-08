"""The founder's life (M24, formulas.md 32.8): stress and its causes, burnout, the personal
account, the foundation, persona traits with causes, influence by region with exposure as a
word, scandals and the legacy score. Never the scandal risk or a scandal's chance."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from tst.api.schemas.founder_parts import LegacyOut, StressOut
from tst.api.schemas.people import EnergyOut


class TraitOut(BaseModel):
    key: str
    label: str
    value: float
    strong: bool = Field(description="At the effect line or above: its effects apply")
    effects: str


class TraitCauseOut(BaseModel):
    turn: int
    date_label: str
    trait: str
    change: float
    cause: str


class PersonaOut(BaseModel):
    traits: list[TraitOut]
    top: str
    effect_at: float
    causes: list[TraitCauseOut]


class PersonalEntryOut(BaseModel):
    turn: int
    date_label: str
    memo: str
    source: str
    amount_cents: int = Field(description="The change in personal cash (gifts are negative)")


class PersonalOut(BaseModel):
    """The founder's own book (32.2): never a company's money."""

    cash_cents: int
    endowment_cents: int
    income: dict[str, int] = Field(description="Lifetime income by source")
    gifts_cents: int
    grants_cents: int
    stake_shares: int = Field(description="Shares the founder holds in the current company")
    stake_value_cents: int | None = Field(description="Shares x the share price once listed")
    can_sell: bool = Field(description="Listed: the founder may sell shares into the float")
    entries: list[PersonalEntryOut] = Field(description="The last entries, newest first")


class FoundationOut(BaseModel):
    name: str
    cause: str
    cause_label: str
    city: str | None
    region: str | None
    created_label: str
    endowment_cents: int
    gifts_cents: int
    grants_cents: int = Field(description="Lifetime grants")
    last_grant_cents: int
    last_grant_label: str | None
    effect: str | None = Field(description="The running effect of the last grants, in words")
    effect_until_label: str | None


class FoundationFormOut(BaseModel):
    can_create: bool
    min_cents: int
    energy: int
    causes: list[str]


class ScandalOut(BaseModel):
    turn: int
    date_label: str
    region: str
    region_label: str


class InfluenceOut(BaseModel):
    region: str
    region_label: str
    influence: float = Field(description="0-100")
    monthly_cents: int
    spent_cents: int
    exposure: Literal["low", "medium", "high"] = Field(
        description="The scandal exposure as a word only (32.5)"
    )
    antitrust_cut_pct: float = Field(description="Antitrust block chance cut by influence, %")
    scandals: int


class RegionOptionOut(BaseModel):
    key: str
    label: str


class GovernmentOut(BaseModel):
    """The Government affairs panel (32.5)."""

    regions: list[InfluenceOut]
    scandals: list[ScandalOut]
    energy: int
    max_monthly_cents: int
    region_options: list[RegionOptionOut] = Field(description="Every region")


class FounderOut(BaseModel):
    founder_name: str
    stress: StressOut
    persona: PersonaOut
    personal: PersonalOut
    foundation: FoundationOut | None
    foundation_form: FoundationFormOut
    government: GovernmentOut
    legacy: LegacyOut


class FounderActionOut(BaseModel):
    founder: FounderOut
    energy: EnergyOut
    unread_inbox: int


class SellSharesIn(BaseModel):
    shares: int = Field(gt=0)


class FoundationIn(BaseModel):
    cause: str
    name: str = ""
    city: str | None = None


class GiftIn(BaseModel):
    amount_cents: int = Field(gt=0)


class LobbyingIn(BaseModel):
    region: str
    monthly_dollars: int = Field(ge=0)
