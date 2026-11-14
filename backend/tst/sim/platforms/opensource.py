"""Open source (docs/formulas.md 44.6).

Open-sourcing a product is a one-off: its base becomes free. Customers rise toward
`base x adoption` over `months` (capped by the addressable market); revenue comes only from the
paid tier (`paid_share` of customers, by category); the community multiplies the product's
feature gain by `feature_mult` (products.phases.develop reads `feature_mult`); an open OS or
developer platform gains tools and goodwill (phase). Closing it again costs goodwill on every
platform the company owns, and a rival forks the open version: a product of the category's
largest other seller, with its features.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.geo.models import RegionalSegment
from tst.sim.log import LogItem, inbox_item
from tst.sim.platforms.models import OpenSource
from tst.sim.platforms.phase import customers_in, home_of
from tst.sim.products.models import SELLING, Product, ProductSegment
from tst.sim.state import GameState, with_product, with_product_segment, with_regional_segment

ADOPTION_PACE: Final = 3.0  # tunable-exempt: customers close a third of the gap a month
ADOPTION_CAP: Final = 0.9  # tunable-exempt: an open product never takes a whole segment


def open_of(state: GameState, product_id: int) -> OpenSource | None:
    return next(
        (o for o in state.open_sources if o.product_id == product_id and o.closed_turn is None),
        None,
    )


def revenue_shares(state: GameState, balance: Balance) -> dict[int, float]:
    """Open products book only their paid tier (44.6)."""
    paid = balance.platforms.open_source.paid_share
    out = {}
    for o in state.open_sources:
        if o.closed_turn is not None:
            continue
        product = state.product(o.product_id)
        if product is not None:
            out[o.product_id] = paid.get(
                product.category, balance.platforms.open_source.default_paid_share
            )
    return out


def feature_mult(state: GameState, product_id: int, balance: Balance) -> float:
    return balance.platforms.open_source.feature_mult if open_of(state, product_id) else 1.0


def adoption_month(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Customers move a third of the way a month toward `base x (1 + (adoption - 1) x
    min(1, months / months_total))` (44.6), every segment and region in proportion, never past
    ADOPTION_CAP of a segment's addressable market."""
    ob = balance.platforms.open_source
    for o in state.open_sources:
        product = state.product(o.product_id)
        if o.closed_turn is not None or product is None or product.status not in SELLING:
            continue
        rows: list[ProductSegment | RegionalSegment] = [
            *state.segments_of(product.id),
            *state.regional_segments_of(product.id),
        ]
        now = sum(r.customers for r in rows)
        if now <= 0:
            continue
        months = state.turn - o.turn
        target = max(o.base_customers, 1.0) * (1 + (ob.adoption - 1) * min(1.0, months / ob.months))
        if now >= target:
            continue
        scale = 1 + (target - now) / now / ADOPTION_PACE
        for row in rows:
            market = (
                state.market(product.category, row.segment)
                if isinstance(row, ProductSegment)
                else state.regional_market(product.category, row.segment, row.region)
            )
            cap = market.addressable * ADOPTION_CAP if market is not None else row.customers
            updated = replace(row, customers=max(row.customers, min(cap, row.customers * scale)))
            if isinstance(updated, ProductSegment):
                state = with_product_segment(state, updated)
            else:
                state = with_regional_segment(state, updated)
    return state


def open_product(state: GameState, product: Product, balance: Balance, data: GameData) -> GameState:
    home = home_of(state, balance, data)
    base = sum(customers_in(state, product, r, home) for r in data.region_keys)
    record = OpenSource(product_id=product.id, turn=state.turn, base_customers=base)
    state = replace(state, open_sources=(*state.open_sources, record))
    platforms = tuple(
        replace(p, open_turn=state.turn) if p.product_id == product.id else p
        for p in state.platforms
    )
    return replace(state, platforms=platforms)


def close_product(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Closing again (44.6): goodwill falls on the owner's platforms, and a rival forks it."""
    ob = balance.platforms.open_source
    sources = tuple(
        replace(o, closed_turn=state.turn)
        if o.product_id == product.id and o.closed_turn is None
        else o
        for o in state.open_sources
    )
    owned = {p.id for p in state.platforms if p.owner_id == product.company_id}
    lo = balance.platforms.goodwill[0]
    rows = tuple(
        replace(r, goodwill=max(lo, r.goodwill - ob.close_goodwill_loss))
        if r.platform_id in owned
        else r
        for r in state.platform_regions
    )
    state = replace(state, open_sources=sources, platform_regions=rows)
    state, fork = _fork(state, product)
    logs = []
    if fork is not None:
        logs.append(
            inbox_item(
                state.turn,
                product.company_id,
                "platform_forked",
                link_kind="product",
                link_id=product.id,
                product=product.name,
                fork=fork.name,
            )
        )
    return state, logs


def _fork(state: GameState, product: Product) -> tuple[GameState, Product | None]:
    """The category's largest other seller ships the open version as its own product."""
    sellers: dict[int, float] = {}
    for p in state.products:
        if (
            p.category == product.category
            and p.company_id != product.company_id
            and p.status in SELLING
        ):
            total = sum(s.customers for s in state.segments_of(p.id))
            sellers[p.company_id] = sellers.get(p.company_id, 0.0) + total
    company = state.company(max(sellers, key=lambda c: (sellers[c], -c))) if sellers else None
    if company is None or not company.alive:
        return state, None
    product_id, ids = state.next_ids.take("product")
    fork = Product(
        id=product_id,
        company_id=company.id,
        category=product.category,
        name=f"{product.name} fork",
        status="live",
        quality=product.quality,
        feature_points=product.feature_points,
        brand=min(product.brand, 30.0),  # tunable-exempt: a new name's brand
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
    )
    state = replace(with_product(state, fork), next_ids=ids)
    for seg in state.segments_of(product.id):
        state = with_product_segment(
            state, ProductSegment(product_id, seg.segment, seg.price_cents, added_turn=state.turn)
        )
    return state, fork
