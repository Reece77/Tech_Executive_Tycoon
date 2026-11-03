"""Selling spare plant capacity: the contract-manufacturing market (docs/formulas.md 26.2).

Like M12a's Cloud hosting (22.3): a company's contract-manufacturing product is an ordinary
product in the `hardware.capacity_category` market, except that
- its quality is its plants' yield x reliability (weighted by live capacity) and its features
  follow the market's expectation from its devices lead, set each month in phase 4;
- its customers' units (units_per_customer a month each) are capped by its plants' spare
  run capacity after its own products, at the end of phase 5.

Rivals' plants are abstract (Foxconn and Pegatron always have capacity), so this applies to
the player's companies only (`player_companies`).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities import formulas as ff
from tst.sim.facilities.lifecycle import staffing
from tst.sim.hardware.production import ProductionPlan, live_plants, plant_yield_of, spare_units
from tst.sim.products.formulas import held_feature_points
from tst.sim.products.models import SELLING, Product
from tst.sim.research import levels
from tst.sim.state import (
    GameState,
    player_companies,
    with_product,
    with_product_segment,
    with_regional_segment,
)

EPS = 1e-9  # tunable-exempt: float tolerance on units
DEVICES = "devices"  # tech_frontier.yaml domain behind contract-manufacturing features


def cm_product(state: GameState, company_id: int, balance: Balance) -> Product | None:
    """The company's contract-manufacturing product, if it sells plant capacity (one)."""
    key = balance.hardware.capacity_category
    for p in state.company_products(company_id):
        if p.status != "retired" and p.category == key:
            return p
    return None


def plant_quality(state: GameState, company_id: int, balance: Balance) -> float | None:
    """yield x reliability across live plants, weighted by live capacity (26.2)."""
    rows = [
        (
            f.live_capacity(state.turn),
            plant_yield_of(f, balance) * staffing(state, f, balance).reliability,
        )
        for f in live_plants(state, company_id, balance)
    ]
    total = sum(c for c, _ in rows)
    return sum(c * q for c, q in rows) / total if total else None


def refresh_product(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> GameState:
    """Phase 4: the product's quality and feature score for this month."""
    product = cm_product(state, company_id, balance)
    if product is None:
        return state
    category = data.category(product.category)
    c = balance.compute
    target = ff.feature_target(
        levels.lead(state, company_id, DEVICES), c.feature_base, c.feature_per_lead
    )
    quality = plant_quality(state, company_id, balance)
    return with_product(
        state,
        replace(
            product,
            quality=product.quality if quality is None else quality,
            feature_points=held_feature_points(target, category, state.turn),
            rotting=False,
        ),
    )


def trim_to_capacity(
    state: GameState, plan: ProductionPlan | None, balance: Balance, data: GameData
) -> tuple[GameState, dict[tuple[int, str], float], dict[int, float]]:
    """Cap each player company's contract-manufacturing customers by its plants' spare run
    units (all regions together, home first). Returns the state, customers removed per
    (product, home segment), and run units sold per plant."""
    removed: dict[tuple[int, str], float] = {}
    sold_by_plant: dict[int, float] = {}
    for company in player_companies(state):
        product = cm_product(state, company.id, balance)
        if product is None or product.status not in SELLING:
            continue
        units = {m.segment: m.units_per_customer for m in data.category(product.category).markets}
        spare = spare_units(state, company.id, plan, balance)
        cap = sum(spare.values())
        home_rows = state.segments_of(product.id)
        abroad = state.regional_segments_of(product.id)
        sold = sum(s.customers * units[s.segment] for s in home_rows) + sum(
            r.customers * units[r.segment] for r in abroad
        )
        if sold > cap + EPS:
            factor = cap / sold if sold > 0 else 0.0
            for seg in home_rows:
                kept = seg.customers * factor
                removed[(product.id, seg.segment)] = seg.customers - kept
                state = with_product_segment(state, replace(seg, customers=kept))
            for rseg in abroad:
                state = with_regional_segment(
                    state, replace(rseg, customers=rseg.customers * factor)
                )
            sold = cap
        left = sold
        for fid in sorted(spare):
            take = min(left, spare[fid])
            if take > EPS:
                sold_by_plant[fid] = take
                left -= take
    return state, removed, sold_by_plant
