"""The 2010 market: addressable demand and the incumbents (formulas.md 11.1, 11.9, ADR-0017).

Used at new game (turn 0) and when an older save is upgraded (migration 0008), where demand
is grown to the save's turn and incumbents start with the same shares of it.
"""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.calendar import turn_to_ym, ym_to_turn
from tst.sim.data_models import GameData, incumbent_regions
from tst.sim.geo.formulas import regional_d0, regional_growth, regional_price_cents
from tst.sim.geo.models import ProductRegion, RegionalMarket, RegionalSegment
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
    # M9 (19.5): other regions' markets and the incumbents' sales there
    regional_markets: tuple[RegionalMarket, ...] = ()
    product_regions: tuple[ProductRegion, ...] = ()
    regional_segments: tuple[RegionalSegment, ...] = ()


def addressable_at(data: GameData, category: str, segment: str, turn: int) -> float:
    """D0 grown by (1 + g)^(1/12) for each month before `turn` (11.1, no noise); g is the
    month's year's growth for a category with growth_by_year (18.6)."""
    cat = data.category(category)
    value = cat.market(segment).addressable
    if not cat.growth_by_year:
        return value * monthly_growth(cat, 0) ** turn
    for t in range(turn):
        value *= monthly_growth(cat, turn_to_ym(t)[0])
    return value


def regional_addressable_at(
    data: GameData, category: str, segment: str, region: str, home: str, turn: int
) -> float:
    """A region's D0 (home D0 x size, 19.5) grown at the category's growth x the region's
    multiplier for each month before `turn`."""
    cat = data.category(category)
    value = regional_d0(cat.market(segment).addressable, region, home, data)
    for t in range(turn):
        value *= regional_monthly_growth(data, category, region, turn_to_ym(t)[0])
    return value


def regional_monthly_growth(data: GameData, category: str, region: str, year: int) -> float:
    """(1 + g x region multiplier)^(1/12) (19.5)."""
    cat = data.category(category)
    return (1 + regional_growth(cat.growth_in(year), region, data)) ** (1 / 12)


def initial_market(
    data: GameData,
    *,
    turn: int,
    first_company_id: int,
    first_product_id: int,
    home: str | None = None,
) -> InitialMarket:
    """Every market segment and every incumbent, in data-file order, as of `turn`.

    `home` (M9): the home region; other regions get markets and the incumbents listed there
    (19.5). None (migration 0008, older saves): v1's markets and incumbents only."""
    markets = tuple(
        MarketSegment(cat.key, m.segment, addressable_at(data, cat.key, m.segment, turn))
        for cat in data.categories
        for m in cat.markets
    )
    demand = {(m.category, m.segment): m.addressable for m in markets}
    regional: list[RegionalMarket] = []
    if home is not None and data.region_markets:
        regional = [
            RegionalMarket(
                cat.key,
                m.segment,
                region,
                regional_addressable_at(data, cat.key, m.segment, region, home, turn),
            )
            for cat in data.categories
            for m in cat.markets
            for region in data.region_keys
            if region != home
        ]
    regional_demand = {(m.category, m.segment, m.region): m.addressable for m in regional}
    companies: list[CompanyState] = []
    products: list[Product] = []
    segments: list[ProductSegment] = []
    launches: list[ProductRegion] = []
    abroad: list[RegionalSegment] = []
    product_id = first_product_id
    incumbents = data.incumbents
    if home is None:  # v1's incumbents: none that list their own regions
        incumbents = tuple(
            inc for inc in incumbents if all(p.regions is None for p in inc.products)
        )
    for offset, inc in enumerate(incumbents):
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
            regions = incumbent_regions(spec)
            # v1 incumbents (no regions listed) sell at home whatever the home region is
            # (19.5: the home region's markets are exactly v1's); regional incumbents only
            # where they are listed.
            at_home = home is None or spec.regions is None or home in regions
            for seg in cat.segment_keys:  # categories.yaml order
                if seg not in spec.segments or not at_home:
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
            for region in regions if regional else ():
                if region == home:
                    continue
                launches.append(ProductRegion(product_id, region, turn, turn))
                for seg in cat.segment_keys:
                    if seg not in spec.segments:
                        continue
                    value = spec.segments[seg]
                    # A regional incumbent's prices are already its region's (incumbents.yaml).
                    price = (
                        value.price_cents
                        if spec.regions is not None
                        else regional_price_cents(value.price_cents, region, home or "", data)
                    )
                    abroad.append(
                        RegionalSegment(
                            product_id=product_id,
                            region=region,
                            segment=seg,
                            price_cents=price,
                            customers=regional_demand[(spec.category, seg, region)]
                            * value.share_bp
                            / BP_DENOMINATOR,
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
        regional_markets=tuple(sorted(regional, key=lambda m: (m.category, m.segment, m.region))),
        product_regions=tuple(sorted(launches, key=lambda r: (r.product_id, r.region))),
        regional_segments=tuple(sorted(abroad, key=lambda s: (s.product_id, s.region, s.segment))),
    )
