"""Incumbent products launched after a game's start (M50, ADR-0024; formulas.md 60.2).

A game begun before 2010 starts without the incumbents.yaml products that went on sale later
(GitHub in April 2008, FarmVille in June 2009; `IncumbentProduct.launched`). Each joins at the
start of its launch month: with no customers before 2010, and with its share of the market in
January 2010 for a product launched in 2010 or later, as a 2010 game has it from turn 0.

A 2010 game starts with every product, so this step never adds one there. It draws nothing.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.hiring.models import INCUMBENT_PRODUCT_BLOCK, INCUMBENT_PRODUCT_IDS_FROM
from tst.sim.products.setup import incumbent_product, launch_turn
from tst.sim.rivals.models import INCUMBENT_KEY
from tst.sim.state import GameState


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
