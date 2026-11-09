"""World screen schemas (M22, formulas.md 39): blocs, tension, the export rules announced so far
(in force, coming, ended or suspended), licences, compliant variants, the entity list and the
player's exposure. Never a rule before its announced month, a seeded escalation or détente
before it happens, or the chances that drive them."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class CountryOut(BaseModel):
    key: str
    label: str
    region: str
    bloc: str
    demand_share: float


class TensionPointOut(BaseModel):
    turn: int
    label: str
    value: float
    shock: str = Field(description="none, escalation or detente")


class RuleOut(BaseModel):
    key: str
    title: str
    actor: str
    actor_label: str
    goods: list[str]
    destinations: list[str]
    regime: str
    approval: float | None = Field(description="A licence regime's base approval chance")
    quota: float | None
    threshold: float | None
    status: str = Field(description="in_force, coming, ended or suspended")
    month: str
    announced: str
    end: str | None
    suspended_until: str | None
    effect: str = Field(description="applies, news (shown only) or m19 (M19's mine rules)")
    tag: str | None
    source: str
    seeded: bool


class LicenceOut(BaseModel):
    id: int
    company_id: int
    product_id: int
    product: str
    rule_key: str
    rule: str
    country: str
    country_label: str
    status: str
    requested: str
    decision: str
    until: str | None
    chance: float | None = Field(description="Approval chance with your influence (pending)")


class VariantOut(BaseModel):
    product_id: int
    product: str
    launched: str
    voided_by: list[str] = Field(description="Rules in force that do not accept it")


class ListingOut(BaseModel):
    company_id: int
    company: str
    actor_label: str
    since: str
    reason: str


class RegionAccessOut(BaseModel):
    region: str
    blocked: float
    variant: float


class ProductExposureOut(BaseModel):
    product_id: int
    product: str
    company_id: int
    regions: list[RegionAccessOut]
    licensable: list[str] = Field(description="Countries where a licence can be requested")
    restricted: list[str] = Field(description="Countries where a biting rule restricts it")
    variant_possible: bool
    has_variant: bool
    tariff_cents: int = Field(description="Last month's units at this month's tariff rates")


class SupplyExposureOut(BaseModel):
    company_id: int
    company: str
    good: str
    good_label: str
    exposed: float
    allocation: float
    premium: float
    rule: str | None


class SiteOut(BaseModel):
    company_id: int
    company: str
    country: str
    country_label: str
    bloc: str
    local_partner: bool
    partner_needed: bool


class TariffOut(BaseModel):
    key: str
    title: str
    origin: str
    market: str
    goods: list[str]
    rate: float = Field(description="This month's rate on the goods' cost")
    tag: str


class WorldOut(BaseModel):
    turn: int
    tension: float
    tension_history: list[TensionPointOut]
    countries: list[CountryOut]
    rules: list[RuleOut]
    licences: list[LicenceOut]
    variants: list[VariantOut]
    listings: list[ListingOut]
    products: list[ProductExposureOut]
    supply: list[SupplyExposureOut]
    sites: list[SiteOut]
    tariffs: list[TariffOut] = Field(description="Tariff schedules in force this month")


class LicenceIn(BaseModel):
    product_id: int
    country: str


class GreyRouteIn(BaseModel):
    product_id: int
    country: str
    on: bool = True


class VariantIn(BaseModel):
    product_id: int


class PartnerIn(BaseModel):
    company_id: int | None = None


class WorldActionOut(BaseModel):
    world: WorldOut
    energy: EnergyOut
    unread_inbox: int
