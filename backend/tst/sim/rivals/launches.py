"""Incumbent products launched after a game's start (M50, ADR-0024; formulas.md 60.2).

A game begun before 2010 starts without the incumbents.yaml products that went on sale later
(GitHub in April 2008, FarmVille in June 2009; `IncumbentProduct.launched`). Each joins at the
start of its launch month: with no customers before 2010, and with its share of the market in
January 2010 for a product launched in 2010 or later, as a 2010 game has it from turn 0.

A 2010 game starts with every product, so this step never adds one there. It draws nothing.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.calendar import ym_to_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.finance.insolvency import fail_rival
from tst.sim.hiring.models import INCUMBENT_PRODUCT_BLOCK, INCUMBENT_PRODUCT_IDS_FROM
from tst.sim.products.setup import incumbent_product, launch_turn
from tst.sim.rivals.models import INCUMBENT_KEY, RivalMove
from tst.sim.state import GameState, with_product_segment, with_regional_segment


def incumbent_launches(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Month end: put on sale each incumbent product whose launch month is next month."""
    joining = state.turn + 1
    pending = [
        (index, k, spec)
        for index, inc in enumerate(data.incumbents)
        for k, spec in enumerate(inc.products)
        if launch_turn(spec) == joining
    ]
    if not pending:
        return state
    have = {p.id for p in state.products}
    by_key = {c.rival_key: c for c in state.companies if c.rival_key}
    region = data.city(state.player.hq_city or balance.geo.default_hq_city).region
    regional = bool(data.region_markets)
    demand = {(m.category, m.segment): m.addressable for m in state.markets}
    regional_demand = {
        (m.category, m.segment, m.region): m.addressable for m in state.regional_markets
    }
    products, segments = list(state.products), list(state.product_segments)
    launches, abroad = list(state.product_regions), list(state.regional_segments)
    for index, k, spec in pending:
        product_id = INCUMBENT_PRODUCT_IDS_FROM + index * INCUMBENT_PRODUCT_BLOCK + k
        company = by_key.get((INCUMBENT_KEY, index))
        if product_id in have or company is None or not company.alive:
            continue
        built = incumbent_product(
            data,
            spec,
            company.id,
            product_id,
            joining,
            region,
            regional,
            demand,
            regional_demand,
            empty=joining < 0,
        )
        products.append(built.product)
        segments += built.segments
        launches += built.regions
        abroad += built.abroad
    return replace(
        state,
        products=tuple(sorted(products, key=lambda p: p.id)),
        product_segments=tuple(sorted(segments, key=lambda s: (s.product_id, s.segment))),
        product_regions=tuple(sorted(launches, key=lambda r: (r.product_id, r.region))),
        regional_segments=tuple(sorted(abroad, key=lambda s: (s.product_id, s.region, s.segment))),
    )


def incumbent_exits(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, tuple[RivalMove, ...]]:
    """M50b (60.6), month end: a 2000-world company leaves in its real exit month (Compaq into
    HP in May 2002, Sun into Oracle in January 2010, Nortel's bankruptcy in January 2009). Its
    customers move to `exit_into`'s live product in the same category (the one with the most
    customers, then the lowest id), segment by segment and region by region; with no such
    product, or no `exit_into`, they return to the market. It then closes as a failed rival
    does (15.1), told as market news. Only history_only companies exit, so a 2008 or 2010 game
    never reaches this. It draws nothing."""
    leaving = state.turn + 1
    due = [
        (index, inc)
        for index, inc in enumerate(data.incumbents)
        if inc.exit is not None and ym_to_turn(*inc.exit) == leaving
    ]
    if not due:
        return state, ()
    from tst.sim.rivals.startups import record_move  # M50b: startups imports this module's peers

    moves: list[RivalMove] = []
    by_key = {c.rival_key: c for c in state.companies if c.rival_key}
    by_name = {c.name: c for c in state.companies if c.alive}
    for index, inc in due:
        company = by_key.get((INCUMBENT_KEY, index))
        if company is None or not company.alive:
            continue
        buyer = by_name.get(inc.exit_into) if inc.exit_into else None
        if buyer is not None:
            state = _move_customers(state, company.id, buyer.id)
        state, _ = fail_rival(
            state,
            state.company(company.id),
            balance.hiring.candidate_shelf_turns,
            balance.rivals.free_agent_months,
        )
        why = f"merged into {buyer.name}" if buyer is not None else "closed"
        state, move = record_move(state, state.company(company.id), "failed", why)
        moves.append(move)
    return state, tuple(moves)


def _move_customers(state: GameState, seller_id: int, buyer_id: int) -> GameState:
    """Each of the seller's live products' customers to the buyer's live product in the same
    category with the most customers (then the lowest id), by segment and by region."""
    buyer_products = [p for p in state.company_products(buyer_id) if p.status == "live"]
    for product in state.company_products(seller_id):
        if product.status != "live":
            continue
        same = [p for p in buyer_products if p.category == product.category]
        if not same:
            continue
        target = max(same, key=lambda p: (sum(s.customers for s in state.segments_of(p.id)), -p.id))
        theirs = {s.segment: s for s in state.segments_of(target.id)}
        for seg in state.segments_of(product.id):
            if seg.segment in theirs and seg.customers > 0:
                into = theirs[seg.segment]
                state = with_product_segment(
                    state, replace(into, customers=into.customers + seg.customers)
                )
                state = with_product_segment(state, replace(seg, customers=0.0))
        abroad = {(s.region, s.segment): s for s in state.regional_segments_of(target.id)}
        for rs in state.regional_segments_of(product.id):
            if (rs.region, rs.segment) in abroad and rs.customers > 0:
                into_r = abroad[(rs.region, rs.segment)]
                state = with_regional_segment(
                    state, replace(into_r, customers=into_r.customers + rs.customers)
                )
                state = with_regional_segment(state, replace(rs, customers=0.0))
    return state
