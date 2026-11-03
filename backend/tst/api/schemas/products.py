"""Product and market schemas (M3a).

What the API may show (formulas.md 11.13): quality, feature score, brand, price, appeal,
customers, share of the segment's customers, MRR and churn rate for every product in a
market (incumbents' scores are public). For the player's own products also: assigned units,
builders, sellers and marketers by name, and a development-pace label. Never Q_cap, d_i,
o_i, sales capacity or per-person contributions; a capacity limit is shown only as a note.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.common import BreakdownOut
from tst.api.schemas.people import ActiveEffectOut, EnergyOut


class AppealWeightsOut(BaseModel):
    """How a segment's buyers weigh the four scores (formulas.md 11.6); they sum to 1."""

    quality: float
    price: float
    brand: float
    features: float


class CategorySegmentOut(BaseModel):
    segment: str
    label: str
    reach: str = Field(description="self_serve (awareness) or sales (sales capacity)")
    addressable: int = Field(description="Addressable customers now, rounded")
    reference_price_cents: int
    hosting_cents: int = Field(description="Hosting cost per customer per month")
    weights: AppealWeightsOut
    counts_users: bool = Field(description="Customers are consumer users, not businesses")


class CategoryOut(BaseModel):
    key: str
    label: str
    annual_growth: float = Field(description="Addressable demand growth per year (fraction)")
    segments: list[CategorySegmentOut]
    note: str | None = Field(default=None, description="e.g. compute costs follow the market (M8)")
    launch_quality: float | None = Field(default=None, description="Quality a launch needs (M8)")
    capacity_market: bool = Field(
        default=False,
        description="Sells spare data-centre capacity; not a product to create (M12a)",
    )


class MarketProductOut(BaseModel):
    product_id: int
    name: str
    company_id: int
    company_name: str
    is_player: bool
    status: str
    quality: float
    feature_score: float
    brand: float
    price_cents: int
    price_score: float
    appeal: float
    customers: float
    share_of_served: float = Field(description="Share of the segment's served customers, 0-1")
    churn_rate: float = Field(description="Monthly churn at the current scores, 0-1")
    mrr_cents: int = Field(description="Customers x price this month")


class MarketSegmentOut(BaseModel):
    segment: str
    label: str
    reach: str
    addressable: int
    served: float = Field(description="Customers of every product in the segment")
    unserved: float = Field(description="Addressable customers who use no product yet")
    reference_price_cents: int = Field(description="The segment's typical monthly price")
    weights: AppealWeightsOut
    counts_users: bool
    player_sells: bool = Field(description="The player has a product selling here")
    products: list[MarketProductOut] = Field(description="Most customers first")


class RegionOptionOut(BaseModel):
    key: str
    label: str
    home: bool = Field(description="The HQ's region, whose markets are v1's (19.5)")


class MarketOut(BaseModel):
    category: str
    label: str
    annual_growth: float = Field(description="Addressable demand growth per year (fraction)")
    segments: list[MarketSegmentOut]
    region: str | None = Field(default=None, description="The region shown (M9)")
    region_label: str | None = None
    regions: list[RegionOptionOut] = Field(default_factory=list, description="Region picker")


class NamedOut(BaseModel):
    person_id: int
    name: str


class AssignedUnitOut(BaseModel):
    unit_id: int | None = Field(description="Null for the company root")
    name: str


class ProductSegmentOut(BaseModel):
    segment: str
    label: str
    reach: str
    price_cents: int | None
    price_score: float | None = Field(description="Null until a price is set")
    customers: float
    appeal: float | None = Field(description="Null until a price is set")
    share_of_served: float
    churn_rate: float | None = Field(description="Null unless the product is selling here")
    mrr_cents: int
    new_last_month: float = Field(description="New customers in the last closed month")
    churned_last_month: float = Field(description="Customers lost in the last closed month")
    counts_users: bool
    note: str | None = Field(
        description="'Sales capacity limited new customers in <segment>' when it bound"
    )
    share_breakdown: BreakdownOut | None = Field(
        default=None, description="Share and the appeal inputs behind it (M7b tooltip)"
    )


class ProductMonthOut(BaseModel):
    turn: int
    date_label: str
    segment: str
    quality: float
    feature_score: float
    brand: float
    appeal: float | None
    customers: float
    new: float
    churned: float
    revenue_cents: int


class ProductTotalMonthOut(BaseModel):
    """One month end across every segment of a product (the 12-month chart)."""

    turn: int
    date_label: str
    customers: float
    revenue_cents: int


class TeamStrengthOut(BaseModel):
    """The team's output against the two lines that matter (11.4; 23.4, M10b)."""

    estimated_output: float = Field(
        description="Builder output a month as you can judge it: from the displayed ranges "
        "and noticed tags (est.; ADR-0007)"
    )
    maintains: float = Field(description="Below this the product slips (0.25 x scope)")
    full_speed: float = Field(description="Quality and features at full speed (scope)")
    builders_to_add: int = Field(description="About how many builders to reach the next line")
    text: str = Field(description="The line the product screen shows")


class RegionalPriceOut(BaseModel):
    """A price the product charges in another region (19.5; M10b)."""

    region: str
    region_label: str
    segment: str
    segment_label: str
    price_cents: int | None
    default_price_cents: int = Field(description="p_ref x the region's price index")
    live: bool = Field(description="Selling there now (false while localizing)")


class LaunchReadinessOut(BaseModel):
    ready: bool
    missing: list[str] = Field(description="What still stands between it and launch")


class ProductOut(BaseModel):
    product_id: int
    name: str
    division_id: int | None = Field(default=None, description="Owning division; null = corporate")
    division_name: str | None = None
    category: str
    category_label: str
    status: str
    lifecycle_label: str = Field(description="In development, Growth, Mature, or Sunset")
    quality: float
    feature_score: float
    brand: float
    marketing_budget_cents: int
    created_turn: int
    launched_turn: int | None
    launched_label: str | None = Field(description="Launch month, e.g. 'Sep 2010'")
    mrr_cents: int = Field(description="MRR now, in every region")
    mrr_change: float | None = Field(
        description="Home-region revenue in the last closed month against the month before, "
        "as a fraction (series_scope)"
    )
    customers: float = Field(
        description="Customers (or users) across its segments now, in every region"
    )
    customer_trend: float | None = Field(
        description="Month-on-month change in home-region customers at the last month end, "
        "as a fraction (series_scope)"
    )
    new_last_month: float = Field(description="Home region (series_scope)")
    churned_last_month: float = Field(description="Home region (series_scope)")
    hosting_cents: int = Field(
        description="Hosting this month at the current customers, in every region"
    )
    sells_abroad: bool = Field(
        description="It has customers in a region other than the home region"
    )
    series_scope: str = Field(
        description="What mrr_change, customer_trend, new/churned last month, history and "
        "monthly cover: product history stays home-only (M9; M10r)",
    )
    series_label: str = Field(description="series_scope, for display")
    brand_trend: str = Field(description="rising | falling | steady, from the last two months")
    counts_users: bool = Field(description="Every segment counts consumer users")
    segments: list[ProductSegmentOut]
    active_effects: list[ActiveEffectOut] = Field(
        description="Event modifiers on this product (23.2, M10b)"
    )
    team_strength: TeamStrengthOut | None = Field(
        description="Output against the maintenance and full-speed lines (23.4); null if retired"
    )
    regional_prices: list[RegionalPriceOut] = Field(
        description="Its prices in other regions it has launched in (M10b)"
    )
    assigned_units: list[AssignedUnitOut]
    builders: list[NamedOut]
    sellers: list[NamedOut]
    marketers: list[NamedOut]
    pace: str = Field(description="fast | steady | slow")
    rotting: bool = Field(description="Nobody works on it, so quality is falling")
    quality_breakdown: BreakdownOut | None = Field(
        default=None, description="Quality now, last month's change and the pace (M7b)"
    )
    launch: LaunchReadinessOut
    history: list[ProductMonthOut] = Field(
        description="Last 12 months, oldest first, home region (series_scope)"
    )
    monthly: list[ProductTotalMonthOut] = Field(
        description="Last 12 months summed over segments, oldest first, home region"
    )


class ProductActionOut(BaseModel):
    product: ProductOut
    energy: EnergyOut
    unread_inbox: int


class CreateProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category: str
    segments: list[str] = Field(min_length=1)


class PriceIn(BaseModel):
    segment: str
    price_cents: int


class SegmentIn(BaseModel):
    segment: str


class AssignIn(BaseModel):
    unit_id: int | None = Field(description="Null for the company root")


class MarketingIn(BaseModel):
    budget_cents: int


class PricePreviewOut(BaseModel):
    """Appeal and share* at a price against the current competitors; no customer numbers."""

    segment: str
    price_cents: int
    price_score: float
    appeal: float
    choice_share: float = Field(description="share* among live products and no purchase, 0-1")
    current_price_cents: int | None
    current_price_score: float | None
    current_appeal: float | None
    current_choice_share: float | None
    revenue_per_customer_change: float | None = Field(
        description="New price against the current one, as a fraction; null without a price"
    )


class PortfolioOut(BaseModel):
    """The Products screen's tiles: the company's revenue and product costs."""

    mrr_cents: int = Field(description="Revenue in the last closed month")
    mrr_change: float | None = Field(description="Against the month before, as a fraction")
    previous_label: str | None = Field(description="The month compared against, e.g. 'May'")
    arr_cents: int
    stage: int
    stage_label: str
    paying_customers: float = Field(
        description="Business customers across products now, in every region"
    )
    consumer_users: float = Field(description="Consumer users across products now, every region")
    hosting_cents: int = Field(description="Hosting this month at the current customers")
    marketing_cents: int = Field(description="Marketing budgets this month")
    product_costs_cents: int = Field(description="Hosting plus marketing this month")


class ProductsMetaOut(BaseModel):
    """Energy costs and launch thresholds for the product screens (formulas.md 6, 11.2)."""

    energy_costs: dict[str, int] = Field(description="By action key, e.g. create_product")
    start_quality: float = Field(description="A new product's quality")
    launch_min_quality: float
    launch_min_feature: float
