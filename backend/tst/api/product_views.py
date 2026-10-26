"""Build product and market responses (M3a) from the state and the sim's formulas.

Everything shown is public (formulas.md 11.13): scores, prices, appeal, customers, shares,
churn and MRR. Team output, Q_cap, skills and sales capacity stay inside; the team appears
only as names and a pace label, and a capacity limit only as a note.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tst.api.schemas.products import (
    AssignedUnitOut,
    CategoryOut,
    CategorySegmentOut,
    LaunchReadinessOut,
    MarketOut,
    MarketProductOut,
    MarketSegmentOut,
    NamedOut,
    PricePreviewOut,
    ProductMonthOut,
    ProductOut,
    ProductSegmentOut,
)
from tst.api.views import person_name
from tst.loader import LoadedData
from tst.sim.actions.products import launch_problems
from tst.sim.calendar import format_turn
from tst.sim.errors import ProductRuleError
from tst.sim.org.rules import org_view
from tst.sim.products import formulas as f
from tst.sim.products.models import SELLING, Product, ProductMonth, ProductSegment
from tst.sim.products.phases import current_feature, segment_appeal, shown_turn, team_of
from tst.sim.state import GameState

STATUS_LABELS = {"in_development": "In development", "sunset": "Sunset", "retired": "Retired"}
LIVE_LABEL, GROWTH_LABEL, MATURE_LABEL = "Live", "Growth", "Mature"


@dataclass(frozen=True, slots=True)
class _Row:
    product: Product
    seg: ProductSegment
    appeal: float


def _rows(state: GameState, category: str, segment: str, data: LoadedData) -> list[_Row]:
    """Products selling in one segment (live or sunset, priced), with their appeal now."""
    turn = shown_turn(state)
    products = {p.id: p for p in state.products}
    rows = []
    for seg in state.product_segments:
        product = products.get(seg.product_id)
        if product is None or product.category != category or seg.segment != segment:
            continue
        if product.status not in SELLING or seg.price_cents is None:
            continue
        appeal = segment_appeal(product, seg, data.game_data, turn)
        assert appeal is not None
        rows.append(_Row(product, seg, appeal))
    return rows


def _best(rows: Sequence[_Row]) -> float:
    return max((r.appeal for r in rows if r.product.status == "live"), default=0.0)


def _churn(row: _Row, rows: Sequence[_Row], data: LoadedData) -> float:
    seg_def = data.game_data.segment(row.seg.segment)
    return f.churn_rate(
        seg_def.base_churn,
        _best(rows),
        row.appeal,
        row.product.quality,
        row.product.status == "sunset",
        data.balance.market,
    )


def _mrr(seg: ProductSegment) -> int:
    return round(seg.customers * (seg.price_cents or 0))


def _addressable(state: GameState, category: str, segment: str) -> int:
    market = state.market(category, segment)
    return round(market.addressable) if market else 0


def categories_out(state: GameState, data: LoadedData) -> list[CategoryOut]:
    return [
        CategoryOut(
            key=cat.key,
            label=cat.label,
            annual_growth=cat.growth,
            segments=[
                CategorySegmentOut(
                    segment=m.segment,
                    label=data.game_data.segment(m.segment).label,
                    reach=data.game_data.segment(m.segment).reach,
                    addressable=_addressable(state, cat.key, m.segment),
                    reference_price_cents=m.reference_price_cents,
                    hosting_cents=m.hosting_cents,
                )
                for m in cat.markets
            ],
        )
        for cat in data.game_data.categories
    ]


def market_out(state: GameState, category: str, data: LoadedData) -> MarketOut:
    if category not in {c.key for c in data.game_data.categories}:
        raise ProductRuleError(f"unknown category {category!r}")
    cat = data.game_data.category(category)
    turn = shown_turn(state)
    segments = []
    for m in cat.markets:
        seg_def = data.game_data.segment(m.segment)
        rows = _rows(state, category, m.segment, data)
        served = sum(r.seg.customers for r in rows)
        products = [
            MarketProductOut(
                product_id=r.product.id,
                name=r.product.name,
                company_id=r.product.company_id,
                company_name=state.company(r.product.company_id).name,
                is_player=state.company(r.product.company_id).is_player,
                status=r.product.status,
                quality=r.product.quality,
                feature_score=current_feature(r.product, data.game_data, turn),
                brand=r.product.brand,
                price_cents=r.seg.price_cents or 0,
                appeal=r.appeal,
                customers=r.seg.customers,
                share_of_served=r.seg.customers / served if served else 0.0,
                churn_rate=_churn(r, rows, data),
                mrr_cents=_mrr(r.seg),
            )
            for r in sorted(rows, key=lambda r: (-r.seg.customers, r.product.id))
        ]
        segments.append(
            MarketSegmentOut(
                segment=m.segment,
                label=seg_def.label,
                reach=seg_def.reach,
                addressable=_addressable(state, category, m.segment),
                served=served,
                products=products,
            )
        )
    return MarketOut(category=cat.key, label=cat.label, segments=segments)


def lifecycle_label(product: Product, history: Sequence[ProductMonth], data: LoadedData) -> str:
    """In development / Sunset by status; a live product is Growth if its customers rose more
    than 5% a month over the last 6 months, else Mature (11.2, display only)."""
    if product.status != "live":
        return STATUS_LABELS[product.status]
    pb = data.balance.products
    totals: dict[int, float] = {}
    for row in history:
        totals[row.turn] = totals.get(row.turn, 0.0) + row.customers
    turns = sorted(totals)
    if len(turns) < 2:
        return LIVE_LABEL
    now = turns[-1]
    window = [t for t in turns if t >= now - pb.growth_label_months]
    then = window[0]
    months = now - then
    if totals[then] <= 0:
        return GROWTH_LABEL if totals[now] > 0 else LIVE_LABEL
    rate = (totals[now] / totals[then]) ** (1 / months) - 1
    return GROWTH_LABEL if rate > pb.growth_label_rate else MATURE_LABEL


def product_out(
    state: GameState, product: Product, history: Sequence[ProductMonth], data: LoadedData
) -> ProductOut:
    """One of the player's products, with its team by name (11.13)."""
    game = data.game_data
    company = state.company(product.company_id)
    team = team_of(state, org_view(state, company.id), product, data.balance, game)
    category = game.category(product.category)
    segments = []
    for seg in state.segments_of(product.id):
        seg_def = game.segment(seg.segment)
        rows = _rows(state, product.category, seg.segment, data)
        served = sum(r.seg.customers for r in rows)
        mine = next((r for r in rows if r.product.id == product.id), None)
        segments.append(
            ProductSegmentOut(
                segment=seg.segment,
                label=seg_def.label,
                reach=seg_def.reach,
                price_cents=seg.price_cents,
                customers=seg.customers,
                appeal=segment_appeal(product, seg, game, shown_turn(state)),
                share_of_served=seg.customers / served if served else 0.0,
                churn_rate=None if mine is None else _churn(mine, rows, data),
                mrr_cents=_mrr(seg),
                note=(
                    f"Sales capacity limited new customers in {seg_def.label}"
                    if seg.capacity_limited
                    else None
                ),
            )
        )

    def names(ids: Sequence[int]) -> list[NamedOut]:
        return [NamedOut(person_id=p, name=person_name(state.person(p))) for p in ids]

    missing = launch_problems(state, product, data.balance, game)
    recent = sorted(history, key=lambda m: (m.turn, m.segment))
    last_turns = sorted({m.turn for m in recent})[-12:]
    return ProductOut(
        product_id=product.id,
        name=product.name,
        category=product.category,
        category_label=category.label,
        status=product.status,
        lifecycle_label=lifecycle_label(product, history, data),
        quality=product.quality,
        feature_score=current_feature(product, game, shown_turn(state)),
        brand=product.brand,
        marketing_budget_cents=product.marketing_budget_cents,
        created_turn=product.created_turn,
        launched_turn=product.launched_turn,
        mrr_cents=sum(s.mrr_cents for s in segments),
        segments=segments,
        assigned_units=[
            AssignedUnitOut(
                unit_id=u,
                name=company.name if u is None else _unit_name(state, u),
            )
            for u in team.unit_ids
        ],
        builders=names([b.person_id for b in team.builders]),
        sellers=names([s.person_id for s in team.sellers]),
        marketers=names([m.person_id for m in team.marketers]),
        pace=f.pace(team.base_output(data.balance), category.scope, data.balance.products),
        rotting=product.rotting,
        launch=LaunchReadinessOut(
            ready=product.status == "in_development" and not missing,
            missing=missing if product.status == "in_development" else [],
        ),
        history=[
            ProductMonthOut(
                turn=m.turn,
                date_label=format_turn(m.turn),
                segment=m.segment,
                quality=m.quality,
                feature_score=m.feature_score,
                brand=m.brand,
                appeal=m.appeal,
                customers=m.customers,
                new=m.new,
                churned=m.churned,
                revenue_cents=m.revenue_cents,
            )
            for m in recent
            if m.turn in last_turns
        ],
    )


def _unit_name(state: GameState, unit_id: int) -> str:
    unit = state.unit(unit_id)
    return unit.name if unit is not None else f"Unit {unit_id}"


def price_preview(
    state: GameState, product: Product, segment: str, price_cents: int, data: LoadedData
) -> PricePreviewOut:
    """Appeal and share* at `price_cents` against today's live competitors (11.6, 11.7)."""
    game = data.game_data
    seg = state.product_segment(product.id, segment)
    if seg is None:
        raise ProductRuleError(f"{product.name} does not sell to segment {segment!r}")
    if isinstance(price_cents, bool) or price_cents <= 0:
        raise ProductRuleError("a price must be a positive amount in cents")
    seg_def = game.segment(segment)
    reference = game.category(product.category).market(segment).reference_price_cents
    turn = shown_turn(state)
    others = [
        r.appeal
        for r in _rows(state, product.category, segment, data)
        if r.product.status == "live" and r.product.id != product.id
    ]
    score = f.price_score(reference, price_cents)
    appeal = f.appeal(
        seg_def.weights,
        product.quality,
        score,
        product.brand,
        current_feature(product, game, turn),
    )
    shares, _ = f.choice_shares([appeal, *others], seg_def.outside_option, data.balance.market)
    current = segment_appeal(product, seg, game, turn)
    current_share = None
    if current is not None:
        now, _ = f.choice_shares([current, *others], seg_def.outside_option, data.balance.market)
        current_share = now[0]
    return PricePreviewOut(
        segment=segment,
        price_cents=price_cents,
        price_score=score,
        appeal=appeal,
        choice_share=shares[0],
        current_appeal=current,
        current_choice_share=current_share,
    )
