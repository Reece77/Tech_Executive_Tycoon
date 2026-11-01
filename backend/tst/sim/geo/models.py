"""Frozen geography models (docs/formulas.md 19, M9).

The home region's markets stay in `GameState.markets` and `product_segments` exactly as in
v1; other regions' markets and a product's sales there live in the tuples below.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type OfficeStatus = Literal["open", "closed"]

ANYWHERE = "anywhere"  # a remote unit's search: every candidate's city drawn (19.3)


@dataclass(frozen=True, slots=True)
class Office:
    """A leased office (19.2). GameState holds open offices; a closed one keeps its row."""

    id: int
    company_id: int
    city: str  # cities.yaml key
    seats: int
    opened_turn: int
    status: OfficeStatus = "open"
    closed_turn: int | None = None


@dataclass(frozen=True, slots=True)
class RegionalMarket:
    """Addressable customers D for one category and segment in a region other than the home
    region (19.5); grows in phase 9 at the category's growth x the region's multiplier."""

    category: str
    segment: str
    region: str
    addressable: float


@dataclass(frozen=True, slots=True)
class ProductRegion:
    """A product launched in a region other than the home region (19.5): it sells there
    from `live_turn`."""

    product_id: int
    region: str
    launched_turn: int
    live_turn: int

    def live(self, turn: int) -> bool:
        return turn >= self.live_turn


@dataclass(frozen=True, slots=True)
class RegionalSegment:
    """One segment a product sells to in a region other than the home region (19.5)."""

    product_id: int
    region: str
    segment: str
    price_cents: int | None
    customers: float = 0.0
    capacity_limited: bool = False
    added_turn: int = 0
