"""The M8 multipliers on output, capacity and marketing, in 18.5 order (docs/formulas.md).

Phase 3: builder output = sum(person output x lambda x support x embedded x CTO) x coord(n)
x cross-division x noise; features gain that x CPO. Phase 5: seller capacity x lambda x
support x embedded x CRO. Phase 9: marketing points x support x CMO.

`modifiers` returns None when nothing applies (no divisions and seats not in play), so v1
companies and rivals take exactly the v1 path.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tst.sim.data_models import Balance, GameData
from tst.sim.org import executives as ex
from tst.sim.org.divisions import (
    company_divisions,
    is_scaleup,
    pool_of,
    product_division_spread,
    product_pool,
    support_pools,
    unit_depth,
)
from tst.sim.org.formulas import layer_factor, support_factor, support_morale
from tst.sim.org.rules import OrgView
from tst.sim.products.models import Product
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class Modifiers:
    builder: Mapping[int, float]  # person id -> lambda x support x embedded x CTO
    seller: Mapping[int, float]  # person id -> lambda x support x embedded x CRO
    pool_support: Mapping[int | None, float]  # pool -> support factor
    cpo: float
    cmo: float
    cross_division: float

    def output_factor(self, state: GameState, view: OrgView, product: Product) -> float:
        """The cross-division factor when the product's units span divisions (18.2)."""
        return self.cross_division if len(product_division_spread(state, view, product)) > 1 else 1

    def marketing_factor(self, state: GameState, product: Product) -> float:
        return self.pool_support.get(product_pool(state, product), 1.0) * self.cmo


def modifiers(
    state: GameState, view: OrgView, balance: Balance, data: GameData
) -> Modifiers | None:
    company = state.company(view.company_id)
    seats = ex.seats_in_play(state, company.id, balance)
    if not seats and not company_divisions(state, company.id):
        return None
    org = balance.org
    k = ex.k_coo(state, company.id, balance)
    pools = support_pools(state, view, balance, data) if is_scaleup(company, balance) else {}
    factors = {key: support_factor(p.coverage, k, org) for key, p in pools.items()}
    cto = ex.multiplier(state, company.id, ex.CTO, balance)
    cro = ex.multiplier(state, company.id, ex.CRO, balance)
    builder: dict[int, float] = {}
    seller: dict[int, float] = {}
    for person_id, unit_id in view.unit_of.items():
        base = layer_factor(unit_depth(view.units, unit_id), k, org)
        pool = pool_of(view, person_id)
        base *= factors.get(pool, 1.0)
        if pool is not None:  # an embedded division (18.4)
            base *= org.embedded_bonus
        builder[person_id] = base * cto
        seller[person_id] = base * cro
    return Modifiers(
        builder=builder,
        seller=seller,
        pool_support=factors,
        cpo=ex.multiplier(state, company.id, ex.CPO, balance),
        cmo=ex.multiplier(state, company.id, ex.CMO, balance),
        cross_division=org.cross_division_factor,
    )


def support_morale_terms(
    state: GameState, view: OrgView, balance: Balance, data: GameData
) -> dict[int, float]:
    """W_support per staff member (18.4); empty before stage 3."""
    company = state.company(view.company_id)
    if not is_scaleup(company, balance):
        return {}
    pools = support_pools(state, view, balance, data)
    return {
        person_id: support_morale(pools[pool_of(view, person_id)].coverage, balance.org)
        for person_id in view.unit_of
    }
