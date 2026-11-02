"""Marketing by region (docs/formulas.md 23.5, M10b). A product's marketing budget may be split
across the regions it sells in; by default the split follows revenue. Brand stays global; a
region's self-serve awareness is x (no_marketing_awareness + (1 - no_marketing_awareness) x
min(1, its share / its revenue share)): full at the default split, 70% with no spend. A
product that sells only in its home region is unchanged (v1's market).
"""

from __future__ import annotations

from tst.sim.data_models import Balance
from tst.sim.geo.models import MarketingSplit
from tst.sim.products.models import Product
from tst.sim.state import GameState

BP = 10_000  # tunable-exempt: basis points


def selling_regions(state: GameState, product: Product, home: str) -> list[str]:
    """Home first, then each region the product is live in, in launch order by region key."""
    live = sorted(
        r.region
        for r in state.product_regions
        if r.product_id == product.id and r.live(state.turn) and r.region != home
    )
    return [home, *live]


def revenue_shares(state: GameState, product: Product, home: str) -> dict[str, float]:
    """Each selling region's share of the product's revenue now (home all of it with none)."""
    regions = selling_regions(state, product, home)
    revenue = {r: 0.0 for r in regions}
    revenue[home] = sum(s.customers * (s.price_cents or 0) for s in state.segments_of(product.id))
    for rs in state.regional_segments_of(product.id):
        if rs.region in revenue:
            revenue[rs.region] += rs.customers * (rs.price_cents or 0)
    total = sum(revenue.values())
    if total <= 0:
        return {r: 1.0 if r == home else 0.0 for r in regions}
    return {r: v / total for r, v in revenue.items()}


def split(state: GameState, product: Product, home: str) -> dict[str, float]:
    """The budget's share by selling region: the player's split (renormalized over the regions
    still selling), else revenue shares."""
    regions = selling_regions(state, product, home)
    rows = [m for m in state.marketing_splits if m.product_id == product.id and m.region in regions]
    total = sum(m.share_bp for m in rows)
    if not rows or total <= 0:
        return revenue_shares(state, product, home)
    shares = {r: 0.0 for r in regions}
    for m in rows:
        shares[m.region] = m.share_bp / total
    return shares


def awareness_factors(
    state: GameState, product: Product, home: str, balance: Balance
) -> dict[str, float]:
    """Each selling region's awareness factor (23.5); {} when it sells only at home."""
    regions = selling_regions(state, product, home)
    if len(regions) < 2:  # tunable-exempt: a split needs two regions
        return {}
    base = balance.markets.no_marketing_awareness
    shares = split(state, product, home)
    default = revenue_shares(state, product, home)
    out = {}
    for r in regions:
        s, d = shares.get(r, 0.0), default.get(r, 0.0)
        if s <= 0:
            out[r] = base
        elif d <= 0:
            out[r] = 1.0
        else:
            out[r] = base + (1 - base) * min(1.0, s / d)
    return out


def split_rows(product_id: int, shares: dict[str, int]) -> tuple[MarketingSplit, ...]:
    return tuple(MarketingSplit(product_id, r, bp) for r, bp in sorted(shares.items()))
