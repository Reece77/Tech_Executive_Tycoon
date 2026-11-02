"""Selling spare capacity: the Cloud and GPU hosting market (docs/formulas.md 22.3).

A company's Cloud hosting product is an ordinary product in the `cloud_hosting` category,
except that:
- its quality is its data centres' mean reliability and its features come from its
  infrastructure lead (50 + 2 x lead, at most 100), set each month in phase 4;
- its customers' CU are capped by the spare capacity in each region and its neighbour, after
  its own products (`compute.spare_by_region`), each month at the end of phase 5.

Rivals' capacity is abstract in M12a (they always have enough), so the cap applies only to
the player's companies (`player_companies`).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities import compute
from tst.sim.facilities import formulas as ff
from tst.sim.facilities.lifecycle import mean_reliability
from tst.sim.products.formulas import held_feature_points
from tst.sim.products.models import SELLING
from tst.sim.state import (
    GameState,
    player_companies,
    with_product,
    with_product_segment,
    with_regional_segment,
)

EPS = 1e-9  # tunable-exempt: float tolerance on CU


def infrastructure_lead(state: GameState, company_id: int) -> float:
    """The company's infrastructure lead from the R&D tree (21.1). M11 provides
    `research.lead(state, company_id, "infrastructure")`; until it is merged the lead is 0."""
    del state, company_id
    return 0.0


def refresh_product(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> GameState:
    """The Cloud hosting product's quality (mean reliability) and feature score (from the
    infrastructure lead) for this month (22.3)."""
    product = compute.capacity_product(state, company_id, data)
    if product is None or product.status == "retired":
        return state
    category = data.category(product.category)
    c = balance.compute
    target = ff.feature_target(
        infrastructure_lead(state, company_id), c.feature_base, c.feature_per_lead
    )
    rel = mean_reliability(state, company_id, balance)
    return with_product(
        state,
        replace(
            product,
            quality=product.quality if rel is None else rel,
            feature_points=held_feature_points(target, category, state.turn),
            rotting=False,
        ),
    )


def trim_to_capacity(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, dict[tuple[int, str], float]]:
    """Cap each player company's Cloud hosting customers by its spare capacity, region by
    region (22.3). Returns the state and the customers removed per (product, home segment)."""
    removed: dict[tuple[int, str], float] = {}
    for company in player_companies(state):
        product = compute.capacity_product(state, company.id, data)
        if product is None or product.status not in SELLING:
            continue
        units = {m.segment: m.units_per_customer for m in data.category(product.category).markets}
        spare = compute.spare_by_region(state, company.id, balance, data)
        home = compute.home_region_of(state, balance, data)

        home_rows = state.segments_of(product.id)
        sold = sum(s.customers * units[s.segment] for s in home_rows)
        cap = spare.get(home, 0.0)
        if sold > cap + EPS:
            factor = cap / sold
            for seg in home_rows:
                kept = seg.customers * factor
                removed[(product.id, seg.segment)] = seg.customers - kept
                state = with_product_segment(state, replace(seg, customers=kept))
        regions = sorted({r.region for r in state.regional_segments_of(product.id)})
        for region in regions:
            rows = state.regional_segments_of(product.id, region)
            sold = sum(s.customers * units[s.segment] for s in rows)
            cap = spare.get(region, 0.0)
            if sold > cap + EPS:
                factor = cap / sold
                for rseg in rows:
                    state = with_regional_segment(
                        state, replace(rseg, customers=rseg.customers * factor)
                    )
    return state, removed
