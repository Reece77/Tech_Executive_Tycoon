"""The Studio, Streaming, Games and Social screens (M55, docs/formulas.md 65). Public figures and
the player's own records only (the brief's hidden-value test): never a title's audience before its
release, a creative lead's ego or loyalty, a lead's true creative or vision (ranges only), or a
seeded era, generation, strike or law before it comes."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class MediaRangeOut(BaseModel):
    lo: int
    hi: int


class TitleOut(BaseModel):
    id: int
    name: str
    kind: str = Field(description="series, film or game")
    genre: str
    stage: str = Field(description="development, released or cancelled")
    budget_cents: int
    spent_cents: int
    book_cents: int = Field(description="Carried as a content asset (1560)")
    amortised_cents: int
    written_off_cents: int
    lead_person_id: int | None
    lead_name: str | None
    lead_walked: bool
    months_done: int
    dev_months: int
    release: str = Field(description="Planned release month (or the month it released)")
    greenlit: str
    overrules: int
    cuts: int
    moves: int
    window: str = Field(description="own (on your video service) or licensed")
    platforms: list[str]
    monetisation: str
    live_service: bool
    store: str
    sequel_of: int | None
    audience: float | None = Field(description="Millions; null before release")
    expected: float | None = Field(description="Millions expected at release; null before")
    quality: float | None = Field(description="Its quality multiplier, shown from release")
    revenue_cents: int = Field(description="Booked (licences, box office, sales, in-app)")
    attributed_cents: int = Field(description="Its share of its own service's revenue (shown)")
    players: float = Field(description="A free-to-play game's current players, millions")
    earned_back: bool


class LeadOut(BaseModel):
    person_id: int
    name: str
    level: str
    creative: MediaRangeOut
    vision: MediaRangeOut
    reputation: float
    fee_cents: int = Field(description="A year")
    deal_to: str | None
    titles: int
    morale: int | None
    busy: bool = Field(description="Leading a title in development")


class LeadOfferOut(BaseModel):
    year: int
    n: int
    name: str
    level: str
    region: str
    creative: MediaRangeOut
    vision: MediaRangeOut
    fee_cents: int = Field(description="A year at signing")
    upfront_share: float
    expires: str


class TitleKindOut(BaseModel):
    key: str
    typical_budget_cents: int
    min_budget_cents: int
    max_budget_cents: int
    dev_months: int


class StudioOut(BaseModel):
    slate: list[TitleOut]
    released: list[TitleOut]
    catalogue_book_cents: int = Field(description="Content assets carried")
    catalogue_value_cents: int = Field(description="Own titles' revenue equivalent, decayed")
    leads: list[LeadOut]
    offers: list[LeadOfferOut]
    kinds: list[TitleKindOut]
    strikes: list[str] = Field(description="Regions on strike this month")
    deal_years: list[int]


class ServiceMonthOut(BaseModel):
    month: str
    customers: float
    revenue_cents: int
    ad_revenue_cents: int
    content_cents: int
    costs_cents: int
    cash_cents: int


class RegionCustomersOut(BaseModel):
    region: str
    label: str
    customers: float
    price_cents: int | None
    market: float
    share: float = Field(description="Of the region's market (social: of its internet users)")


class MediaLicenceOut(BaseModel):
    id: int
    fee_cents: int
    from_month: str
    to_month: str


class MediaServiceOut(BaseModel):
    product_id: int
    name: str
    category: str
    status: str
    regions: list[RegionCustomersOut]
    customers: float
    churn_mult: float = Field(description="Its churn x this (catalogue engagement)")
    engagement: float = Field(description="Catalogue value over the median service's")
    ad_tier: bool
    ad_revenue_cents: int = Field(description="Last month")
    content_cents: int = Field(description="Last month: own titles in production and licences")
    cash_cents: int = Field(description="Cumulative since launch")
    paid_back: str | None
    months: list[ServiceMonthOut]
    licences: list[MediaLicenceOut]


class StreamingOut(BaseModel):
    services: list[MediaServiceOut]
    ad_tier_open: bool
    ad_tier_from: str
    music_payout: float
    licence_years: list[int]


class GameTitleOut(BaseModel):
    title: TitleOut
    decay: float = Field(description="Players lost a month now")


class ConsoleGenerationOut(BaseModel):
    key: str
    label: str
    month: str


class GamesOut(BaseModel):
    titles: list[GameTitleOut]
    generations: list[ConsoleGenerationOut]
    store_fee: float
    epic_fee: float
    epic_open: bool


class LawOut(BaseModel):
    id: int
    region: str
    label: str
    announced: str
    deadline: str
    status: str


class SocialNetworkOut(BaseModel):
    product_id: int
    name: str
    status: str
    regions: list[RegionCustomersOut]
    users: float
    format: str | None
    format_label: str | None
    advantage: bool = Field(description="On the newest format within its window")
    network_effect: float = Field(description="Appeal x this in its largest region")
    ad_load: float
    moderation: str
    ad_revenue_cents: int = Field(description="Last month: users x their ad revenue a user")
    laws: list[LawOut]


class FormatOut(BaseModel):
    key: str
    label: str
    month: str


class AdMarketOut(BaseModel):
    region: str
    label: str
    spend_cents: int = Field(description="A month, game scale")
    digital_cents: int
    impressions_m: float
    cpm_cents: float


class ConsumerAppOut(BaseModel):
    product_id: int
    name: str
    ad_pricing: bool


class SocialOut(BaseModel):
    networks: list[SocialNetworkOut]
    formats: list[FormatOut]
    ads: list[AdMarketOut]
    consumer_apps: list[ConsumerAppOut]
    ad_pricing_open: bool
    load_range: list[float]


class MediaScreenOut(BaseModel):
    studio: StudioOut
    streaming: StreamingOut
    games: GamesOut
    social: SocialOut


class MediaActionOut(BaseModel):
    media: MediaScreenOut
    energy: EnergyOut
    unread_inbox: int


class GreenlightIn(BaseModel):
    name: str
    kind: str
    budget_cents: int
    genre: str = "drama"
    lead_person_id: int | None = None
    unit_id: int | None = None
    sequel_of: int | None = None
    platforms: list[str] = Field(default_factory=list)
    monetisation: str = "premium"
    live_service: bool = False
    store: str = "default"
    window: str = "licensed"
    service_product_id: int | None = None


class CutIn(BaseModel):
    budget_cents: int


class MoveReleaseIn(BaseModel):
    months: int


class LiveServiceIn(BaseModel):
    on: bool


class SignIn(BaseModel):
    year: int
    n: int
    years: int


class MediaLicenceIn(BaseModel):
    product_id: int
    fee_cents: int
    years: int


class MediaLineIn(BaseModel):
    ad_tier: bool = False
    ad_load: float = 1.0
    format: str | None = None
    moderation: str = "standard"
    ad_pricing: bool = False
