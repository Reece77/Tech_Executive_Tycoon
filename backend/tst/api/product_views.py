"""Build product and market responses (M3a) from the state and the sim's formulas.

Everything shown is public (formulas.md 11.13): scores, prices, appeal, customers, shares,
churn and MRR. Q_cap and skills stay inside. Since M10b (23.4) the team's total output is
shown against its maintenance and full-speed lines, and a capacity limit with its numbers,
so every warning says what to do; individual skills never are.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from tst.api import breakdowns
from tst.api.schemas.products import (
    AppealWeightsOut,
    AssignedUnitOut,
    CategoryOut,
    CategorySegmentOut,
    LaunchReadinessOut,
    MarketOut,
    MarketProductOut,
    MarketSegmentOut,
    NamedOut,
    PortfolioOut,
    PricePreviewOut,
    ProductMonthOut,
    ProductOut,
    ProductSegmentOut,
    ProductTotalMonthOut,
    RegionalPriceOut,
    RegionOptionOut,
    TeamStrengthOut,
)
from tst.api.views import person_name, product_effects
from tst.loader import LoadedData
from tst.sim.actions.geo import default_regional_price
from tst.sim.actions.products import launch_problems
from tst.sim.calendar import format_turn, turn_to_ym
from tst.sim.data_models import Balance, SegmentDef
from tst.sim.errors import ProductRuleError
from tst.sim.finance.macro import ai_index
from tst.sim.geo.cities import home_region
from tst.sim.geo.formulas import regional_growth, relative_row
from tst.sim.geo.models import RegionalSegment
from tst.sim.org.rules import org_view
from tst.sim.products import formulas as f
from tst.sim.products.estimates import shown_team
from tst.sim.products.formulas import hosting_cents
from tst.sim.products.models import SELLING, Product, ProductMonth, ProductSegment
from tst.sim.products.phases import (
    builders_to_add,
    current_feature,
    pricing_power,
    product_costs,
    reference_price,
    segment_appeal,
    shown_turn,
    team_of,
)
from tst.sim.products.team import Team
from tst.sim.snapshot import CompanySnapshot
from tst.sim.state import GameState

STATUS_LABELS = {"in_development": "In development", "sunset": "Sunset", "retired": "Retired"}
LIVE_LABEL, GROWTH_LABEL, MATURE_LABEL = "Live", "Growth", "Mature"
CONSUMER_SEGMENT = "consumer"  # customers there are users, shown apart from businesses
# Product history (product_month) stays home-only by decision (M9 brief): its series say so.
HOME_SCOPE, HOME_SCOPE_LABEL = "home_region", "Home region"
BRAND_STEADY = 0.05  # brand points a month below which the brand trend reads "steady"


@dataclass(frozen=True, slots=True)
class _Row:
    product: Product
    seg: ProductSegment | RegionalSegment
    appeal: float


def _rows(
    state: GameState, category: str, segment: str, data: LoadedData, region: str | None = None
) -> list[_Row]:
    """Products selling in one segment (live or sunset, priced), with their appeal now.
    `region`: another region's market (M9, 19.5); None for the home region."""
    turn = shown_turn(state)
    products = {p.id: p for p in state.products}
    index = regional_index(state, region, data)
    rows = []
    segs: list[ProductSegment | RegionalSegment] = (
        list(state.product_segments)
        if region is None
        else [
            r
            for r in state.regional_segments
            if r.region == region
            and (launch := state.product_region(r.product_id, r.region)) is not None
            and launch.live(state.turn)
        ]
    )
    for seg in segs:
        product = products.get(seg.product_id)
        if product is None or product.category != category or seg.segment != segment:
            continue
        if product.status not in SELLING or seg.price_cents is None:
            continue
        power = pricing_power(state, product, data.balance, estimate=True)  # CRO (18.3, 18.8)
        appeal = segment_appeal(product, seg, data.game_data, turn, power, index)
        assert appeal is not None
        rows.append(_Row(product, seg, appeal))
    return rows


def regional_index(state: GameState, region: str | None, data: LoadedData) -> float:
    """A region's price index relative to the home region; 1 at home (19.5)."""
    if region is None:
        return 1.0
    home = home_region(state, data.balance, data.game_data)
    return relative_row(region, home, data.game_data)[1]


def _best(rows: Sequence[_Row]) -> float:
    return max((r.appeal for r in rows if r.product.status == "live"), default=0.0)


def _churn(row: _Row, rows: Sequence[_Row], data: LoadedData, mult: float = 1.0) -> float:
    """`mult`: the CPO and support factors on base churn (M8, 18.3, 18.4)."""
    seg_def = data.game_data.segment(row.seg.segment)
    return f.churn_rate(
        seg_def.base_churn * mult,
        _best(rows),
        row.appeal,
        row.product.quality,
        row.product.status == "sunset",
        data.balance.market,
    )


def _mrr(seg: ProductSegment | RegionalSegment) -> int:
    return round(seg.customers * (seg.price_cents or 0))


def _weights(seg_def: SegmentDef) -> AppealWeightsOut:
    w = seg_def.weights
    return AppealWeightsOut(quality=w.quality, price=w.price, brand=w.brand, features=w.features)


def _price_score(
    state: GameState,
    product: Product,
    seg: ProductSegment | RegionalSegment,
    data: LoadedData,
    index: float = 1.0,
) -> float | None:
    """The price score as sales use it: the reference price (x a region's price index) x the
    CRO's estimated pricing power in a sales-led segment (18.3, 18.8; M8r; 19.5)."""
    if seg.price_cents is None:
        return None
    power = pricing_power(state, product, data.balance, estimate=True)
    reference = reference_price(product, seg.segment, data.game_data, power, index)
    return f.price_score(reference, seg.price_cents)


def _addressable(state: GameState, category: str, segment: str, region: str | None = None) -> int:
    if region is not None:
        rmarket = state.regional_market(category, segment, region)
        return round(rmarket.addressable) if rmarket else 0
    market = state.market(category, segment)
    return round(market.addressable) if market else 0


def categories_out(state: GameState, data: LoadedData) -> list[CategoryOut]:
    return [
        CategoryOut(
            key=cat.key,
            label=cat.label,
            annual_growth=cat.growth_in(turn_to_ym(state.turn)[0]),
            note="Compute costs follow the market" if cat.compute_indexed else None,
            launch_quality=max(data.balance.products.launch_min_quality, cat.launch_quality or 0),
            segments=[
                CategorySegmentOut(
                    segment=m.segment,
                    label=data.game_data.segment(m.segment).label,
                    reach=data.game_data.segment(m.segment).reach,
                    addressable=_addressable(state, cat.key, m.segment),
                    reference_price_cents=m.reference_price_cents,
                    hosting_cents=round(
                        hosting_cents(cat, m.segment, ai_index(state, data.game_data))
                    ),
                    weights=_weights(data.game_data.segment(m.segment)),
                    counts_users=m.segment == CONSUMER_SEGMENT,
                )
                for m in cat.markets
            ],
        )
        for cat in data.game_data.categories
    ]


def market_out(
    state: GameState, category: str, data: LoadedData, region: str | None = None
) -> MarketOut:
    """`region`: a region other than the home region (M9's region picker, 19.7)."""
    if category not in {c.key for c in data.game_data.categories}:
        raise ProductRuleError(f"unknown category {category!r}")
    home = home_region(state, data.balance, data.game_data) if data.game_data.cities else None
    if region == home:
        region = None
    if region is not None and region not in data.game_data.region_keys:
        raise ProductRuleError(f"unknown region {region!r}")
    cat = data.game_data.category(category)
    turn = shown_turn(state)
    index = regional_index(state, region, data)
    segments = []
    for m in cat.markets:
        seg_def = data.game_data.segment(m.segment)
        rows = _rows(state, category, m.segment, data, region)
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
                price_score=_price_score(state, r.product, r.seg, data, index) or 0.0,
                appeal=r.appeal,
                customers=r.seg.customers,
                share_of_served=r.seg.customers / served if served else 0.0,
                churn_rate=_churn(r, rows, data),
                mrr_cents=_mrr(r.seg),
            )
            for r in sorted(rows, key=lambda r: (-r.seg.customers, r.product.id))
        ]
        addressable = _addressable(state, category, m.segment, region)
        segments.append(
            MarketSegmentOut(
                segment=m.segment,
                label=seg_def.label,
                reach=seg_def.reach,
                addressable=addressable,
                served=served,
                unserved=max(0.0, addressable - served),
                reference_price_cents=(
                    m.reference_price_cents
                    if region is None
                    else max(1, round(m.reference_price_cents * index))
                ),
                weights=_weights(seg_def),
                counts_users=m.segment == CONSUMER_SEGMENT,
                player_sells=any(state.company(r.product.company_id).is_player for r in rows),
                products=products,
            )
        )
    year = turn_to_ym(state.turn)[0]
    growth = cat.growth_in(year)
    if region is not None:
        growth = regional_growth(growth, region, data.game_data)
    shown = region or home
    return MarketOut(
        category=cat.key,
        label=cat.label,
        annual_growth=growth,
        segments=segments,
        region=shown,
        region_label=data.game_data.region(shown).label if shown else None,
        regions=[
            RegionOptionOut(key=r.key, label=r.label, home=r.key == home)
            for r in data.game_data.regions
        ]
        if home
        else [],
    )


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
    # Seat effects shown as estimates from displayed ranges (18.8; M8r).
    team = team_of(state, org_view(state, company.id), product, data.balance, game, estimate=True)
    category = game.category(product.category)
    shown = shown_team(state, company.id, team, category, data.balance)  # 23.4: as judged
    months = _months(history)
    last = months[-1] if months else {}
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
                price_score=_price_score(state, product, seg, data),
                customers=seg.customers,
                appeal=(
                    appeal := segment_appeal(
                        product,
                        seg,
                        game,
                        shown_turn(state),
                        pricing_power(state, product, data.balance, estimate=True),
                    )
                ),
                share_of_served=(share := seg.customers / served if served else 0.0),
                churn_rate=None if mine is None else _churn(mine, rows, data, team.churn_mult),
                mrr_cents=_mrr(seg),
                note=capacity_note(shown, seg_def, seg.capacity_limited, data.balance),
                new_last_month=last[seg.segment].new if seg.segment in last else 0.0,
                churned_last_month=last[seg.segment].churned if seg.segment in last else 0.0,
                counts_users=seg.segment == CONSUMER_SEGMENT,
                share_breakdown=breakdowns.market_share(
                    appeal,
                    _price_score(state, product, seg, data),
                    product,
                    current_feature(product, game, shown_turn(state)),
                    {
                        "quality": seg_def.weights.quality,
                        "price": seg_def.weights.price,
                        "brand": seg_def.weights.brand,
                        "features": seg_def.weights.features,
                    },
                    share,
                ),
            )
        )

    def names(ids: Sequence[int]) -> list[NamedOut]:
        return [NamedOut(person_id=p, name=person_name(state.person(p))) for p in ids]

    missing = launch_problems(state, product, data.balance, game)
    abroad = state.regional_segments_of(product.id) if product.status in SELLING else ()
    recent = sorted(history, key=lambda m: (m.turn, m.segment))
    pace = f.pace(team.base_output(data.balance), category.scope, data.balance.products)
    last_turns = sorted({m.turn for m in recent})[-12:]
    division = state.unit(product.division_id) if product.division_id is not None else None
    return ProductOut(
        product_id=product.id,
        name=product.name,
        division_id=division.id if division is not None else None,
        division_name=division.name if division is not None else None,
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
        launched_label=None
        if product.launched_turn is None
        else format_turn(product.launched_turn),
        # Now: home and other regions, as phase 5 books them (M10r finding 4).
        mrr_cents=sum(s.mrr_cents for s in segments) + sum(_mrr(r) for r in abroad),
        mrr_change=_change(months, lambda m: sum(r.revenue_cents for r in m.values())),
        customers=sum(s.customers for s in segments) + sum(r.customers for r in abroad),
        customer_trend=_change(months, lambda m: sum(r.customers for r in m.values())),
        new_last_month=sum(s.new_last_month for s in segments),
        churned_last_month=sum(s.churned_last_month for s in segments),
        hosting_cents=_hosting(state, product, data),
        brand_trend=_brand_trend(months),
        sells_abroad=any(r.customers > 0 for r in abroad),
        series_scope=HOME_SCOPE,
        series_label=HOME_SCOPE_LABEL,
        counts_users=bool(segments) and all(s.counts_users for s in segments),
        segments=segments,
        regional_prices=_regional_prices(state, product, data),
        team_strength=team_strength(product, shown, category.scope, data.balance),
        active_effects=product_effects(state, product.id),
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
        pace=pace,
        rotting=product.rotting,
        quality_breakdown=breakdowns.product_quality(
            product,
            [next(iter(m.values())).quality for m in months],
            pace,
            product.rotting,
        ),
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
        monthly=[
            ProductTotalMonthOut(
                turn=turn,
                date_label=format_turn(turn),
                customers=sum(r.customers for r in rows.values()),
                revenue_cents=sum(r.revenue_cents for r in rows.values()),
            )
            for rows in months
            if (turn := next(iter(rows.values())).turn) in last_turns
        ],
    )


def team_strength(
    product: Product, team: Team, scope: float, balance: Balance
) -> TeamStrengthOut | None:
    """'Output 1.1. Below 1.5 your product slips; full speed at 6. Add about 1 builder to stop
    the slide.' (23.4, M10b)"""
    if product.status == "retired":
        return None
    pb = balance.products
    output = team.base_output(balance)
    maintains = pb.rot_threshold * scope
    n = len(team.builders)
    head = (
        f"Output about {output:.1f} (est.). Below {maintains:.1f} {product.name} slips; "
        f"full speed at {scope:g}."
    )
    if not team.builders:
        add = 1
        text = f"Nobody is working on {product.name}: assign a unit to it. {head}"
    elif output < maintains:
        add = builders_to_add(output, n, maintains)
        text = f"{head} Add about {add} builder{'s' if add != 1 else ''} to stop the slide."
    elif output < scope:
        add = builders_to_add(output, n, scope)
        text = f"{head} About {add} more builder{'s' if add != 1 else ''} reach full speed."
    else:
        add = 0
        text = f"{head} The team is at full speed."
    return TeamStrengthOut(
        estimated_output=round(output, 2),
        maintains=round(maintains, 2),
        full_speed=scope,
        builders_to_add=add,
        text=text,
    )


def capacity_note(team: Team, seg_def: SegmentDef, limited: bool, balance: Balance) -> str | None:
    """'2 sellers win up to 40 SMB customers a month, fewer than wanted to buy. Each extra
    seller adds about 20.' (23.4, M10b); None while capacity is not the limit."""
    if not limited:
        return None
    sellers = len(team.sellers)
    cap = team.capacity(seg_def.key, balance)
    rate = balance.products.seller_rate.get(seg_def.key, 0.0)
    per = cap / sellers if sellers else f.seller_capacity(rate, (1.0,))
    return (
        f"{sellers} seller{'s' if sellers != 1 else ''} win up to about {cap:,.0f} "
        f"{seg_def.label} customers a month (est.), fewer than wanted to buy. Each extra "
        f"seller adds about {per:,.0f}."
    )


def _regional_prices(
    state: GameState, product: Product, data: LoadedData
) -> list[RegionalPriceOut]:
    """Prices in every other region the product launched in, by region then segment (19.5)."""
    game = data.game_data
    out = []
    for region in game.region_keys:
        launch = state.product_region(product.id, region)
        if launch is None:
            continue
        for seg in state.regional_segments_of(product.id, region):
            out.append(
                RegionalPriceOut(
                    region=region,
                    region_label=game.region(region).label,
                    segment=seg.segment,
                    segment_label=game.segment(seg.segment).label,
                    price_cents=seg.price_cents,
                    default_price_cents=default_regional_price(
                        state, product.category, seg.segment, region, data.balance, game
                    ),
                    live=launch.live(state.turn),
                )
            )
    return out


def _months(history: Sequence[ProductMonth]) -> list[dict[str, ProductMonth]]:
    """History rows grouped by month (oldest first), keyed by segment."""
    by_turn: dict[int, dict[str, ProductMonth]] = {}
    for row in history:
        by_turn.setdefault(row.turn, {})[row.segment] = row
    return [by_turn[t] for t in sorted(by_turn)]


def _change(
    months: Sequence[dict[str, ProductMonth]], total: Callable[[dict[str, ProductMonth]], float]
) -> float | None:
    """The last month against the one before, as a fraction; None without two months or with
    nothing the month before."""
    if len(months) < 2:
        return None
    before, now = total(months[-2]), total(months[-1])
    return None if before <= 0 else now / before - 1


def _brand_trend(months: Sequence[dict[str, ProductMonth]]) -> str:
    """rising, falling or steady from the last two month ends (never the target brand)."""
    if len(months) < 2:
        return "steady"
    before = next(iter(months[-2].values())).brand
    now = next(iter(months[-1].values())).brand
    if now - before > BRAND_STEADY:
        return "rising"
    if before - now > BRAND_STEADY:
        return "falling"
    return "steady"


def _hosting(state: GameState, product: Product, data: LoadedData) -> int:
    """round(C x h) per segment this month, home and other regions, as phase 6 will post it
    (11.8, 19.5; M10r finding 4)."""
    if product.status not in SELLING:
        return 0
    category = data.game_data.category(product.category)
    ai = ai_index(state, data.game_data)
    rows: list[ProductSegment | RegionalSegment] = [
        *state.segments_of(product.id),
        *state.regional_segments_of(product.id),
    ]
    return sum(round(seg.customers * hosting_cents(category, seg.segment, ai)) for seg in rows)


def portfolio_out(
    state: GameState,
    snapshots: Sequence[tuple[int, CompanySnapshot]],
    stage_label: str,
    data: LoadedData,
) -> PortfolioOut:
    """The Products screen's tiles (M3b): MRR and ARR from the month-end snapshots, customers
    and this month's hosting and marketing from the current state."""
    company = state.player
    latest = snapshots[-1][1] if snapshots else None
    previous = snapshots[-2] if len(snapshots) >= 2 else None
    mrr = latest.mrr_cents if latest else 0
    change = None
    if previous is not None and previous[1].mrr_cents > 0:
        change = mrr / previous[1].mrr_cents - 1
    users = 0.0
    business = 0.0
    for product in state.company_products(company.id):
        if product.status not in SELLING:
            continue
        rows: list[ProductSegment | RegionalSegment] = [
            *state.segments_of(product.id),
            *state.regional_segments_of(product.id),
        ]
        for seg in rows:
            if seg.segment == CONSUMER_SEGMENT:
                users += seg.customers
            else:
                business += seg.customers
    hosting, marketing = product_costs(state, company.id, data.game_data)
    return PortfolioOut(
        mrr_cents=mrr,
        mrr_change=change,
        previous_label=None if previous is None else format_turn(previous[0]).split(" ")[0],
        arr_cents=latest.arr_cents if latest else 0,
        stage=company.stage,
        stage_label=stage_label,
        paying_customers=business,
        consumer_users=users,
        hosting_cents=hosting,
        marketing_cents=marketing,
        product_costs_cents=hosting + marketing,
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
    power = pricing_power(state, product, data.balance, estimate=True)
    reference = reference_price(product, segment, game, power)  # as the current appeal (M8r)
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
    current = segment_appeal(product, seg, game, turn, power)
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
        current_price_cents=seg.price_cents,
        current_price_score=_price_score(state, product, seg, data),
        current_appeal=current,
        current_choice_share=current_share,
        revenue_per_customer_change=(
            None if seg.price_cents is None else price_cents / seg.price_cents - 1
        ),
    )
