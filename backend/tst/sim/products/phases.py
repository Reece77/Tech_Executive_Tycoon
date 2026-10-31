"""Product and market phases (docs/formulas.md section 11, ADR-0017).

Phase 3 develops products (quality and features), phase 5 runs every market segment
(appeal, churn, in play, choice, new customers, revenue), phase 6 adds hosting and
marketing to the monthly costs, phase 9 updates brand and grows demand, phase 10 applies
the ARR stage gates, and phase 11 writes each product's month-end history.

Incumbents' products are static (ADR-0017): they skip development and brand, and their
feature points follow F_exp so the feature score stays fixed. In the market they are
ordinary products, except that they use awareness 1 and no sales-capacity limit (11.7).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from tst.sim.calendar import MONTHS_PER_YEAR, turn_to_ym
from tst.sim.data_models import SCORE_MAX, Balance, GameData
from tst.sim.ledger import CASH, REVENUE_SUBSCRIPTIONS, LedgerEntry, LedgerLine
from tst.sim.log import LinkKind, LogItem, inbox_item
from tst.sim.money import Cents
from tst.sim.org.executives import CRO, side_factor
from tst.sim.org.rules import OrgView, org_view
from tst.sim.products import formulas as f
from tst.sim.products.models import SELLING, Product, ProductMonth, ProductSegment
from tst.sim.products.team import Team, product_team
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    reach_stage,
    with_company,
    with_market,
    with_product,
    with_product_segment,
    with_unit,
)

CUSTOMER_ROUNDING = 0.5  # tunable-exempt: customers are shown rounded; below this is "none"
PRODUCT_LINK: LinkKind = "product"

type FlowKey = tuple[int, str]  # (product_id, segment)


@dataclass(frozen=True, slots=True)
class Flow:
    """What phase 5 did for one product in one segment."""

    new: float = 0.0
    churned: float = 0.0
    revenue_cents: Cents = 0


def _views(state: GameState) -> dict[int, OrgView]:
    return {c.id: org_view(state, c.id) for c in state.ledger_companies()}


def team_of(
    state: GameState,
    view: OrgView,
    product: Product,
    balance: Balance,
    data: GameData,
    *,
    estimate: bool = False,
) -> Team:
    return product_team(
        state, view, product, data.category(product.category), balance, data, estimate=estimate
    )


def shown_turn(state: GameState) -> int:
    """The turn whose phase 3 last ran: displayed feature scores use its F_exp (11.14)."""
    return max(state.turn - 1, 0)


def current_feature(product: Product, data: GameData, turn: int) -> float:
    return f.feature_score(product.feature_points, data.category(product.category), turn)


def reference_price(
    product: Product, segment: str, data: GameData, pricing_power: float = 1.0
) -> int:
    """The reference price a segment's price score uses: x the CRO's pricing power in a
    sales-led segment (18.3). Sales, the current appeal and a price preview all use this one
    (M8r, Codex review 1 finding 5)."""
    reference = data.category(product.category).market(segment).reference_price_cents
    if pricing_power != 1 and data.segment(segment).reach == "sales":
        reference = round(reference * pricing_power)
    return reference


def segment_appeal(
    product: Product,
    seg: ProductSegment,
    data: GameData,
    turn: int,
    pricing_power: float = 1.0,
) -> float | None:
    """Appeal in one segment from the product's current scores; None without a price. In a
    sales-led segment the reference price is x `pricing_power`, the CRO's pricing power
    (18.3); 1 for v1 companies and rivals."""
    if seg.price_cents is None:
        return None
    reference = reference_price(product, seg.segment, data, pricing_power)
    return f.appeal(
        data.segment(seg.segment).weights,
        product.quality,
        f.price_score(reference, seg.price_cents),
        product.brand,
        current_feature(product, data, turn),
    )


def pricing_power(
    state: GameState, product: Product, balance: Balance, *, estimate: bool = False
) -> float:
    """The CRO's pricing power for the product's company (18.3); 1 before stage 3.
    `estimate`: from the displayed ranges, for the API (M8r)."""
    return side_factor(state, product.company_id, CRO, "pricing", balance, estimate=estimate)


# --- Phase 3: development -------------------------------------------------------------------


def develop(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Quality and features for every product that is not retired, by product id (11.4)."""
    pb = balance.products
    turn = state.turn
    views = _views(state)
    logs: list[LogItem] = []
    for product in state.products:
        if product.status == "retired":
            continue
        category = data.category(product.category)
        if product.is_static:
            assert product.held_feature is not None
            points = f.held_feature_points(product.held_feature, category, turn)
            state = with_product(state, replace(product, feature_points=points))
            continue
        team = team_of(state, views[product.company_id], product, balance, data)
        output = team.base_output(balance)
        if team.builders:
            sd = f.dev_noise_sd(team.mavericks, pb)
            noise = max(0.0, 1 + float(rng.stream(turn, "product_dev", product.id).normal(0, sd)))
            output *= noise
        quality = f.next_quality(product.quality, output, category.scope, team.qcap(balance), pb)
        rotting = f.is_rotting(output, category.scope, pb)
        if rotting and not product.rotting:
            logs.append(
                inbox_item(
                    turn,
                    product.company_id,
                    "product_rotting",
                    link_kind=PRODUCT_LINK,
                    link_id=product.id,
                    product=product.name,
                )
            )
        updated = replace(
            product,
            quality=quality,
            feature_points=product.feature_points + output * team.feature_mult,  # CPO (18.3)
            rotting=rotting,
        )
        state = with_product(state, updated)
    return state, tuple(logs)


# --- Phase 5: customers and revenue ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MarketOutcome:
    state: GameState
    entries: tuple[LedgerEntry, ...]
    logs: tuple[LogItem, ...]
    revenue: Mapping[int, Cents]  # company id -> this month's revenue (MRR)
    flows: Mapping[FlowKey, Flow]


def run_markets(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> MarketOutcome:
    """Every category and segment in categories.yaml order (11.7), then revenue (11.8)."""
    mb = balance.market
    turn = state.turn
    views = _views(state)
    teams: dict[int, Team] = {}
    flows: dict[FlowKey, Flow] = {}
    logs: list[LogItem] = []
    products = {p.id: p for p in state.products}
    by_market: dict[tuple[str, str], list[ProductSegment]] = {}
    for seg in state.product_segments:
        product = products.get(seg.product_id)
        if product is not None and product.status in SELLING and seg.price_cents is not None:
            by_market.setdefault((product.category, seg.segment), []).append(seg)

    def power(product: Product) -> float:
        return 1.0 if product.is_static else team(product).pricing_power

    def churn_mult(product: Product) -> float:
        return 1.0 if product.is_static else team(product).churn_mult

    def team(product: Product) -> Team:
        if product.id not in teams:
            view = views[product.company_id]
            teams[product.id] = team_of(state, view, product, balance, data)
        return teams[product.id]

    for cat in data.categories:
        for market_def in cat.markets:
            entries = by_market.get((cat.key, market_def.segment), [])
            market = state.market(cat.key, market_def.segment)
            if not entries or market is None:
                continue
            seg_def = data.segment(market_def.segment)
            appeals = {
                s.product_id: segment_appeal(
                    products[s.product_id],
                    s,
                    data,
                    turn,
                    power(products[s.product_id]),
                )
                for s in entries
            }
            live = [s for s in entries if products[s.product_id].status == "live"]
            best = max((appeals[s.product_id] or 0.0 for s in live), default=0.0)
            total = sum(s.customers for s in entries)
            unserved = max(0.0, market.addressable - total)
            churned = {
                s.product_id: s.customers
                * f.churn_rate(
                    seg_def.base_churn * churn_mult(products[s.product_id]),  # 18.3, 18.4
                    best,
                    appeals[s.product_id] or 0.0,
                    products[s.product_id].quality,
                    products[s.product_id].status == "sunset",
                    mb,
                )
                for s in entries
            }
            gen = rng.stream(
                turn, "market", data.category_index(cat.key), data.segment_index(seg_def.key)
            )
            noise = max(0.0, 1 + float(gen.normal(0, mb.demand_noise_sd)))
            pool = sum(churned.values()) + seg_def.adoption * unserved
            # In-play customers come from those who churned and the unserved, never more.
            in_play = min(pool * noise, sum(churned.values()) + unserved)
            shares, _ = f.choice_shares(
                [appeals[s.product_id] or 0.0 for s in live], seg_def.outside_option, mb
            )
            won = {s.product_id: 0.0 for s in entries}
            limited: set[int] = set()
            for s, share in zip(live, shares, strict=True):
                product = products[s.product_id]
                wanted = in_play * share
                if product.is_static:
                    won[s.product_id] = wanted
                elif seg_def.reach == "self_serve":
                    aware = min(1.0, f.awareness(product.brand, mb) * team(product).awareness_mult)
                    won[s.product_id] = wanted * aware  # CMO (18.3)
                else:
                    cap = team(product).capacity(seg_def.key, balance)
                    won[s.product_id] = min(wanted, cap)
                    if wanted > cap:
                        limited.add(s.product_id)
            for s in entries:
                product = products[s.product_id]
                customers = max(0.0, s.customers - churned[s.product_id] + won[s.product_id])
                capacity_limited = s.product_id in limited
                if capacity_limited and not s.capacity_limited:
                    logs.append(
                        inbox_item(
                            turn,
                            product.company_id,
                            "sales_capacity_limited",
                            link_kind=PRODUCT_LINK,
                            link_id=product.id,
                            product=product.name,
                            segment=seg_def.label,
                        )
                    )
                state = with_product_segment(
                    state, replace(s, customers=customers, capacity_limited=capacity_limited)
                )
                flows[(s.product_id, s.segment)] = Flow(
                    new=won[s.product_id], churned=churned[s.product_id]
                )

    state, entries_out, revenue, flows, more = _revenue(state, flows, data)
    return MarketOutcome(
        state=state,
        entries=entries_out,
        logs=tuple(logs + more),
        revenue=revenue,
        flows=flows,
    )


def _revenue(
    state: GameState, flows: dict[FlowKey, Flow], data: GameData
) -> tuple[
    GameState, tuple[LedgerEntry, ...], dict[int, Cents], dict[FlowKey, Flow], list[LogItem]
]:
    """round(C x price) per segment for companies with books; sunset products whose last
    customers left retire (11.2, 11.8)."""
    turn = state.turn
    entries: list[LedgerEntry] = []
    revenue: dict[int, Cents] = {c.id: 0 for c in state.ledger_companies()}
    logs: list[LogItem] = []
    for product in state.products:
        if product.status not in SELLING:
            continue
        segments = state.segments_of(product.id)
        booked = 0
        if product.company_id in revenue:
            for seg in segments:
                amount = round(seg.customers * (seg.price_cents or 0))
                booked += amount
                key = (product.id, seg.segment)
                flows[key] = replace(flows.get(key, Flow()), revenue_cents=amount)
            if booked:
                d = product.division_id  # the product's division (M8, 18.1)
                entries.append(
                    LedgerEntry(
                        turn=turn,
                        company_id=product.company_id,
                        memo=f"Revenue: {product.name}",
                        lines=(
                            LedgerLine(CASH, booked, d),
                            LedgerLine(REVENUE_SUBSCRIPTIONS, -booked, d),
                        ),
                    )
                )
            revenue[product.company_id] += booked
        top = max(segments, key=lambda s: s.customers, default=None)
        if (
            product.first_customer_turn is None
            and product.company_id == state.player.id  # a note for the player only (M5)
            and top is not None
            and top.customers >= CUSTOMER_ROUNDING
        ):
            product = replace(product, first_customer_turn=turn)
            state = with_product(state, product)
            logs.append(
                inbox_item(
                    turn,
                    product.company_id,
                    "first_customer",
                    link_kind=PRODUCT_LINK,
                    link_id=product.id,
                    product=product.name,
                    segment=data.segment(top.segment).label,
                    revenue_cents=booked,
                )
            )
        if product.status == "sunset" and all(s.customers < CUSTOMER_ROUNDING for s in segments):
            for seg in segments:
                state = with_product_segment(state, replace(seg, customers=0.0))
            state = with_product(state, replace(product, status="retired", retired_turn=turn))
            state = release_assignments(state, product.id)
    return state, tuple(entries), revenue, flows, logs


def release_assignments(state: GameState, product_id: int) -> GameState:
    """Units (and the root) working on a retired product become free (11.3)."""
    for company in state.companies:
        if company.root_product_id == product_id:
            state = with_company(state, replace(company, root_product_id=None))
    for unit in state.units:
        if unit.product_id == product_id:
            state = with_unit(state, replace(unit, product_id=None))
    return state


def projected_revenue(state: GameState, company_id: int) -> Cents:
    """This month's revenue at the current customers and prices: round(C x price) per
    segment of every selling product, as phase 5 would book it before this month's flows."""
    return sum(
        round(seg.customers * seg.price_cents)
        for product in state.company_products(company_id)
        if product.status in SELLING
        for seg in state.segments_of(product.id)
        if seg.price_cents is not None
    )


# --- Phase 6: hosting and marketing ---------------------------------------------------------


def product_costs_by_division(
    state: GameState, company_id: int, data: GameData
) -> tuple[dict[int | None, Cents], dict[int | None, Cents]]:
    """(hosting, marketing) per division (None = corporate) for one company this month:
    round(C x h) per segment of every selling product, and the budget of every product that
    is not retired (11.8, 18.1)."""
    hosting: dict[int | None, Cents] = {}
    marketing: dict[int | None, Cents] = {}
    year = turn_to_ym(state.turn)[0]
    for product in state.company_products(company_id):
        if product.status == "retired":
            continue
        d = product.division_id
        marketing[d] = marketing.get(d, 0) + product.marketing_budget_cents
        if product.status not in SELLING:
            continue
        category = data.category(product.category)
        for seg in state.segments_of(product.id):
            h = f.hosting_cents(category, seg.segment, data.compute_index, year)
            hosting[d] = hosting.get(d, 0) + round(seg.customers * h)
    return hosting, marketing


def product_costs(state: GameState, company_id: int, data: GameData) -> tuple[Cents, Cents]:
    """(hosting, marketing) for one company this month (11.8)."""
    hosting, marketing = product_costs_by_division(state, company_id, data)
    return sum(hosting.values()), sum(marketing.values())


# --- Phase 9: brand and demand --------------------------------------------------------------


def brand_and_demand(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Brand toward B* for every developing product (11.5); demand grows (11.1)."""
    pb = balance.products
    views = _views(state)
    for product in state.products:
        if product.status == "retired" or product.is_static:
            continue
        category = data.category(product.category)
        team = team_of(state, views[product.company_id], product, balance, data)
        mk = f.marketing_points(product.marketing_budget_cents, team.mu, pb)
        mk *= team.marketing_mult  # support and CMO (M8, 18.5)
        target = f.target_brand(mk, category.brand_constant)
        if team.brand_mult != 1:  # CMO (18.3), at most 100
            target = min(float(SCORE_MAX), target * team.brand_mult)
        state = with_product(state, replace(product, brand=f.next_brand(product.brand, target, pb)))
    year = turn_to_ym(state.turn)[0]
    for market in state.markets:
        growth = f.monthly_growth(data.category(market.category), year)
        state = with_market(state, replace(market, addressable=market.addressable * growth))
    return state


# --- Phase 10: stages from revenue ----------------------------------------------------------


def arr_stages(
    state: GameState, revenue: Mapping[int, Cents], balance: Balance
) -> tuple[GameState, tuple[LogItem, ...]]:
    """ARR = 12 x MRR. Stage 2 from $1M, stage 3 from $20M; stages only rise (11.11).
    The inbox notes the highest ARR milestone passed for the first time."""
    logs: list[LogItem] = []
    for company in state.ledger_companies():
        mrr = revenue.get(company.id, 0)
        arr = arr_of(mrr)
        stage = company.stage
        for gate, threshold in sorted(balance.stages.arr_cents.items()):
            if arr >= threshold and stage < gate:
                stage = gate
        passed = [m for m in balance.products.arr_milestones_cents if arr >= m]
        milestone = company.arr_milestone_cents
        if passed and passed[-1] > milestone and company.is_player:  # rivals: no notes (M5)
            milestone = passed[-1]
            logs.append(
                inbox_item(
                    state.turn,
                    company.id,
                    "arr_milestone",
                    milestone_cents=milestone,
                    arr_cents=arr,
                    mrr_cents=mrr,
                )
            )
        if (stage, milestone) != (company.stage, company.arr_milestone_cents):
            state = with_company(
                state,
                replace(reach_stage(company, stage, state.turn), arr_milestone_cents=milestone),
            )
    return state, tuple(logs)


def arr_of(mrr_cents: Cents) -> Cents:
    """ARR = 12 x MRR (11.8)."""
    return mrr_cents * MONTHS_PER_YEAR


# --- Phase 11: history ----------------------------------------------------------------------


def month_history(
    state: GameState, flows: Mapping[FlowKey, Flow], data: GameData, balance: Balance
) -> tuple[ProductMonth, ...]:
    """Month-end rows for every product that was not already retired, by product and segment."""
    turn = state.turn
    rows = []
    products = {p.id: p for p in state.products}
    for seg in state.product_segments:
        product = products.get(seg.product_id)
        if product is None or (product.status == "retired" and product.retired_turn != turn):
            continue
        flow = flows.get((seg.product_id, seg.segment), Flow())
        rows.append(
            ProductMonth(
                turn=turn,
                product_id=product.id,
                segment=seg.segment,
                quality=product.quality,
                feature_score=current_feature(product, data, turn),
                brand=product.brand,
                appeal=segment_appeal(
                    product, seg, data, turn, pricing_power(state, product, balance)
                ),
                customers=seg.customers,
                new=flow.new,
                churned=flow.churned,
                revenue_cents=flow.revenue_cents,
            )
        )
    return tuple(rows)
