"""The 2010 market: addressable demand and the incumbents (formulas.md 11.1, 11.9, ADR-0017).

Used at new game (turn 0) and when an older save is upgraded (migration 0008), where demand
is grown to the save's turn and incumbents start with the same shares of it.
"""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.calendar import ym_to_turn
from tst.sim.data_models import GameData
from tst.sim.money import BP_DENOMINATOR
from tst.sim.products.formulas import held_feature_points, monthly_growth
from tst.sim.products.models import MarketSegment, Product, ProductSegment
from tst.sim.state import CompanyState

FOUNDED_MONTH = 1  # incumbents' founding is shown by year only


@dataclass(frozen=True, slots=True)
class InitialMarket:
    companies: tuple[CompanyState, ...]
    products: tuple[Product, ...]
    product_segments: tuple[ProductSegment, ...]
    markets: tuple[MarketSegment, ...]
    next_product_id: int


def addressable_at(data: GameData, category: str, segment: str, turn: int) -> float:
    """D0 grown by (1 + g)^(1/12) for each month before `turn` (11.1, no noise)."""
    cat = data.category(category)
    return cat.market(segment).addressable * monthly_growth(cat) ** turn


def initial_market(
    data: GameData, *, turn: int, first_company_id: int, first_product_id: int
) -> InitialMarket:
    """Every market segment and every incumbent, in data-file order, as of `turn`."""
    markets = tuple(
        MarketSegment(cat.key, m.segment, addressable_at(data, cat.key, m.segment, turn))
        for cat in data.categories
        for m in cat.markets
    )
    demand = {(m.category, m.segment): m.addressable for m in markets}
    companies: list[CompanyState] = []
    products: list[Product] = []
    segments: list[ProductSegment] = []
    product_id = first_product_id
    for offset, inc in enumerate(data.incumbents):
        company_id = first_company_id + offset
        companies.append(
            CompanyState(
                id=company_id,
                name=inc.name,
                is_player=False,
                stage=inc.stage,
                founded_turn=ym_to_turn(inc.founded_year, FOUNDED_MONTH),
            )
        )
        for spec in inc.products:
            cat = data.category(spec.category)
            products.append(
                Product(
                    id=product_id,
                    company_id=company_id,
                    category=spec.category,
                    name=spec.name,
                    status="live",
                    quality=spec.quality,
                    feature_points=held_feature_points(spec.features, cat, turn),
                    brand=spec.brand,
                    marketing_budget_cents=0,
                    created_turn=turn,
                    launched_turn=turn,
                    held_feature=spec.features,
                )
            )
            for seg in cat.segment_keys:  # categories.yaml order
                if seg not in spec.segments:
                    continue
                value = spec.segments[seg]
                segments.append(
                    ProductSegment(
                        product_id=product_id,
                        segment=seg,
                        price_cents=value.price_cents,
                        customers=demand[(spec.category, seg)] * value.share_bp / BP_DENOMINATOR,
                        added_turn=turn,
                    )
                )
            product_id += 1
    return InitialMarket(
        companies=tuple(companies),
        products=tuple(products),
        product_segments=tuple(sorted(segments, key=lambda s: (s.product_id, s.segment))),
        markets=tuple(sorted(markets, key=lambda m: (m.category, m.segment))),
        next_product_id=product_id,
    )
