"""The living world's API (M28, docs/formulas.md 41.7, 41.9): World news, the chain companies
by good, and the company page's world section. Public facts only: never a rival's hidden
valuation, a cost position beyond its third of the cost curve, a capex intention before it is
announced, or a region's seeded cycle path."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NamedOut(BaseModel):
    key: str
    label: str


class CompanyRefOut(BaseModel):
    company_id: int
    name: str


class WorldNewsItemOut(BaseModel):
    news_id: int
    turn: int
    date_label: str
    kind: str
    kind_label: str
    message: str
    company: CompanyRefOut | None
    other: CompanyRefOut | None
    region: NamedOut | None
    good: NamedOut | None


class WorldNewsOut(BaseModel):
    started: bool = Field(description="The living world runs from January 2026")
    items: list[WorldNewsItemOut] = Field(description="Newest first, after the filters")
    companies: list[CompanyRefOut] = Field(description="Every company the feed names")
    regions: list[NamedOut]
    goods: list[NamedOut]
    kinds: list[NamedOut]


class ChainProducerOut(BaseModel):
    company_id: int
    name: str
    country_label: str
    capacity_year: float = Field(description="Live capacity a year, the good's volume unit")
    building: float = Field(description="Announced capacity under construction")
    mothballed: float
    share: float = Field(description="Share of the good's live world capacity")
    owner: CompanyRefOut | None


class ChainGoodOut(BaseModel):
    good: str
    label: str
    unit: str
    capacity_year: float
    output_year: float = Field(description="Last month's output a year")
    utilisation: float
    market: str = Field(description="tight, balanced or slack: last month's market")
    producers: list[ChainProducerOut]


class ChainOut(BaseModel):
    started: bool
    goods: list[ChainGoodOut]


class ExecutiveOut(BaseModel):
    role: str
    name: str
    since_label: str


class WorldFacilityOut(BaseModel):
    facility_id: int
    good: str
    good_label: str
    country: str
    country_label: str
    region: str
    capacity_year: float
    unit: str
    status: str = Field(description="live, building, mothballed or closed")
    cost_band: str = Field(description="Its third of the good's cost curve: low, middle or high")
    ready_label: str | None = Field(description="An announced build's month")


class MoneyRangeOut(BaseModel):
    low_cents: int
    high_cents: int


class FinancialsOut(BaseModel):
    listed: bool
    revenue_year_cents: int | None = Field(description="Listed: last month x 12")
    ebitda_year_cents: int | None = Field(description="Listed: the last 12 months")
    revenue_range: MoneyRangeOut | None = Field(description="Private: an estimate")
    ebitda_range: MoneyRangeOut | None


class WorldDealOut(BaseModel):
    date_label: str
    buyer: CompanyRefOut
    target: CompanyRefOut
    price_cents: int
    kind: str
    status: str


class SubsidiaryOut(BaseModel):
    company: CompanyRefOut
    mandate: str
    since_label: str


class OfftakeOut(BaseModel):
    buyer: CompanyRefOut
    seller: CompanyRefOut
    good_label: str
    volume: float
    unit: str
    ends_label: str


class WorldCompanyOut(BaseModel):
    kind: str = Field(description="chain (a miner, refiner or foundry) or tech")
    country_label: str | None
    owner: CompanyRefOut | None
    subsidiaries: list[SubsidiaryOut]
    mandate: str | None = Field(description="What its owner runs it for")
    executives: list[ExecutiveOut]
    facilities: list[WorldFacilityOut]
    financials: FinancialsOut | None
    deals: list[WorldDealOut]
    offtakes: list[OfftakeOut]
    news: list[WorldNewsItemOut]
