"""Displayed numbers the press judges by (29.1, 29.2): a product's market share in its home
segments, its displayed quality and prices, and a company's displayed research lead. Only
what the API shows (rounded as shown), never a hidden value."""

from __future__ import annotations

from tst.sim.state import GameState

BP = 10_000  # tunable-exempt: basis points


def product_share_bp(state: GameState, product_id: int) -> int:
    """The product's customers over every product's in its home segments, in bp."""
    product = state.product(product_id)
    if product is None:
        return 0
    mine = 0.0
    total = 0.0
    for seg in state.segments_of(product_id):
        mine += seg.customers
        for other in state.products:
            if other.category != product.category or other.status == "retired":
                continue
            theirs = state.product_segment(other.id, seg.segment)
            if theirs is not None:
                total += theirs.customers
    return round(mine * BP / total) if total > 0 else 0


def shown_quality(state: GameState, product_id: int) -> int:
    """Quality as every screen shows it: a whole number (the API's value, rounded)."""
    product = state.product(product_id)
    return round(product.quality) if product is not None else 0


def shown_prices(state: GameState, product_id: int) -> dict[str, int]:
    return {
        s.segment: s.price_cents for s in state.segments_of(product_id) if s.price_cents is not None
    }


def shown_lead(state: GameState, company_id: int, domain: str) -> int:
    """The company's own research lead in a domain, as the Research screen shows it."""
    lead = next(
        (r for r in state.research_leads if r.company_id == company_id and r.domain == domain),
        None,
    )
    return round(lead.lead) if lead is not None else 0


def main_rival(state: GameState, product_id: int) -> tuple[int | None, str | None]:
    """The rival company with the most customers in the product's segments, and the segment:
    the rival a launch's press moment can name (29.1)."""
    product = state.product(product_id)
    if product is None:
        return None, None
    best: tuple[float, int, str] | None = None
    for seg in state.segments_of(product_id):
        for other in state.products:
            if other.company_id == product.company_id or other.category != product.category:
                continue
            if other.status not in ("live", "sunset"):
                continue
            if not state.company(other.company_id).is_rival:
                continue
            theirs = state.product_segment(other.id, seg.segment)
            if theirs is not None and (best is None or theirs.customers > best[0]):
                best = (theirs.customers, other.company_id, seg.segment)
    if best is None:
        segs = state.segments_of(product_id)
        return None, segs[0].segment if segs else None
    return best[1], best[2]
