"""Where medical rules meet the market (docs/formulas.md 50.2, 50.4, 50.5): the share of a
region's demand a medical device may win, applied by M22's access map in phase 5 (new wins x
the share; existing customers keep buying and replacing).

share = cleared x coverage x adoption, zero while a recall or a stop holds:
- cleared: the region's people in the parts whose regulator has cleared the device (M34's part
  shares), plus the rest of the region once its reliance registration is in;
- coverage: 1 if the sub-category needs none or the region covers the device, else
  `medical.coverage.no_coverage_share`;
- adoption: 1 for consumer devices, else floor + (1 - floor) x clinicians' adoption there.

Only the player's group's devices are gated: rivals' devices are history's, cleared wherever
they sell (M41 decision)."""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.geopolitics.sales import Access
from tst.sim.medical import coverage as cov
from tst.sim.medical import data as md
from tst.sim.medical import quality
from tst.sim.products.models import Product
from tst.sim.state import GameState


def share(
    state: GameState, product: Product, region: str, balance: Balance, data: GameData
) -> float:
    sub = md.subcategory(data, product.category)
    if sub is None:
        return 1.0
    if quality.blocked(state, product.id):
        return 0.0
    turn = state.turn
    stopped = quality.stopped_parts(state, product.company_id)
    regs = md.in_region(data, region)
    cleared = sum(
        md.part_share(data, r)
        for r in regs
        if r.key not in stopped and md.cleared(state, product.id, r.key, turn)
    )
    if md.cleared(state, product.id, md.RELY + region, turn):
        cleared += md.reliance_share(data, region)
    if cleared <= 0:
        return 0.0
    c = 1.0
    if sub.needs_coverage and not cov.covered(state, product.id, region):
        c = balance.medical.coverage.no_coverage_share
    a = 1.0
    if sub.clinicians:
        floor = balance.medical.adoption.floor
        a = floor + (1 - floor) * cov.adoption(state, product.id, region)
    return min(1.0, cleared) * c * a


def merge(
    access: dict[tuple[int, str], Access], state: GameState, balance: Balance, data: GameData
) -> dict[tuple[int, str], Access]:
    """M22's access map with each designed device's medical share folded in."""
    if not md.enabled(data) or not state.med_designs:
        return access
    out = dict(access)
    for d in state.med_designs:
        product = state.product(d.product_id)
        if product is None or product.status not in ("live", "sunset"):
            continue
        for region in data.region_keys:
            s = share(state, product, region, balance, data)
            a = out.get((product.id, region), Access())
            blocked = 1 - (1 - a.blocked) * s
            if blocked > 0:
                out[(product.id, region)] = Access(blocked, a.variant)
    return out
