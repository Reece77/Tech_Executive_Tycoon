"""Product and market schemas (M3a).

What the API may show (formulas.md 11.13): quality, feature score, brand, price, appeal,
customers, share of the segment's customers, MRR and churn rate for every product in a
market (incumbents' scores are public). For the player's own products also: assigned units,
builders, sellers and marketers by name, and a development-pace label. Never Q_cap, d_i,
o_i, sales capacity or per-person contributions; a capacity limit is shown only as a note.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class CategorySegmentOut(BaseModel):
    segment: str
    label: str
    reach: str = Field(description="self_serve (awareness) or sales (sales capacity)")
    addressable: int = Field(description="Addressable customers now, rounded")
    reference_price_cents: int
    hosting_cents: int = Field(description="Hosting cost per customer per month")


class CategoryOut(BaseModel):
    key: str
    label: str
    annual_growth: float = Field(description="Addressable demand growth per year (fraction)")
    segments: list[CategorySegmentOut]


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
    products: list[MarketProductOut] = Field(description="Most customers first")


class MarketOut(BaseModel):
    category: str
    label: str
    segments: list[MarketSegmentOut]


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
    customers: float
    appeal: float | None = Field(description="Null until a price is set")
    share_of_served: float
    churn_rate: float | None = Field(description="Null unless the product is selling here")
    mrr_cents: int
    note: str | None = Field(
        description="'Sales capacity limited new customers in <segment>' when it bound"
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


class LaunchReadinessOut(BaseModel):
    ready: bool
    missing: list[str] = Field(description="What still stands between it and launch")


class ProductOut(BaseModel):
    product_id: int
    name: str
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
    mrr_cents: int
    segments: list[ProductSegmentOut]
    assigned_units: list[AssignedUnitOut]
    builders: list[NamedOut]
    sellers: list[NamedOut]
    marketers: list[NamedOut]
    pace: str = Field(description="fast | steady | slow")
    rotting: bool = Field(description="Nobody works on it, so quality is falling")
    launch: LaunchReadinessOut
    history: list[ProductMonthOut] = Field(description="Last 12 months, oldest first")


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
    current_appeal: float | None
    current_choice_share: float | None
