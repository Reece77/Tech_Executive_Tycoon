"""Frozen product and market models (docs/formulas.md section 11, ADR-0017).

GameState holds products that are not retired, their segments, and every market segment's
addressable demand. Incumbents' products are ordinary products owned by non-player
companies; `held_feature` marks them as static until M5 (ADR-0017).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type ProductStatus = Literal["in_development", "live", "sunset", "retired"]

PRODUCT_STATUSES: tuple[ProductStatus, ...] = ("in_development", "live", "sunset", "retired")
SELLING: tuple[ProductStatus, ...] = ("live", "sunset")  # have customers who churn (11.7)


@dataclass(frozen=True, slots=True)
class Product:
    id: int
    company_id: int
    category: str  # categories.yaml key
    name: str
    status: ProductStatus
    quality: float  # 0-100
    feature_points: float  # accumulated F (11.4)
    brand: float  # 0-100
    marketing_budget_cents: int
    created_turn: int
    launched_turn: int | None = None
    sunset_turn: int | None = None
    retired_turn: int | None = None
    # An incumbent's fixed feature score: its F follows F_exp so the score stays here (11.9).
    # None for products that develop (the player's, and rivals' from M5).
    held_feature: float | None = None
    first_customer_turn: int | None = None  # first month with at least one paying customer
    rotting: bool = False  # last phase 3 found no team working on it (11.4)
    division_id: int | None = None  # the division it belongs to; None = corporate (M8, 18.1)

    @property
    def is_static(self) -> bool:
        """Fixed scores: no development, no brand change (ADR-0017)."""
        return self.held_feature is not None


@dataclass(frozen=True, slots=True)
class ProductSegment:
    """One segment a product sells to: its price and customers (stored as a float)."""

    product_id: int
    segment: str  # categories.yaml segment key
    price_cents: int | None  # None until set; launch needs a price in every segment
    customers: float = 0.0
    capacity_limited: bool = False  # last phase 5 sales capacity bound new customers (11.13)
    added_turn: int = 0


@dataclass(frozen=True, slots=True)
class MarketSegment:
    """Addressable customers D for one category and segment; grows in phase 9 (11.1)."""

    category: str
    segment: str
    addressable: float


@dataclass(frozen=True, slots=True)
class ProductMonth:
    """One month of history for a product in one segment (append-only, product_month)."""

    turn: int
    product_id: int
    segment: str
    quality: float
    feature_score: float
    brand: float
    appeal: float | None  # None while the segment has no price
    customers: float
    new: float
    churned: float
    revenue_cents: int
