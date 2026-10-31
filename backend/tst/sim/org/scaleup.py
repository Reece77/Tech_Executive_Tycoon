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
from tst.sim.org.formulas import (
    layer_factor,
    support_churn,
    support_factor,
    support_morale,
)
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
    # 18.3 redesign (2026-10-31) and 18.4 churn
    qcap: float = 1.0  # CTO on Q_cap
    churn: float = 1.0  # CPO on base churn
    brand: float = 1.0  # CMO on B*
    awareness: float = 1.0  # CMO on awareness
    pricing: float = 1.0  # CRO on p_ref in sales segments
    pool_churn: Mapping[int | None, float] | None = None  # pool -> support churn factor

    def output_factor(self, state: GameState, view: OrgView, product: Product) -> float:
        """The cross-division factor when the product's units span divisions (18.2)."""
        return self.cross_division if len(product_division_spread(state, view, product)) > 1 else 1

    def marketing_factor(self, state: GameState, product: Product) -> float:
        return self.pool_support.get(product_pool(state, product), 1.0) * self.cmo

    def churn_factor(self, state: GameState, product: Product) -> float:
        """CPO x the support shortfall of the product's pool (18.3, 18.4)."""
        pool = (self.pool_churn or {}).get(product_pool(state, product), 1.0)
        return self.churn * pool


def modifiers(
    state: GameState, view: OrgView, balance: Balance, data: GameData, *, estimate: bool = False
) -> Modifiers | None:
    """Seat, support and structure factors (18.5). `estimate`: seat effects from displayed
    ranges, for the API (M8r); the engine always uses true values."""
    company = state.company(view.company_id)
    seats = ex.seats_in_play(state, company.id, balance)
    if not seats and not company_divisions(state, company.id):
        return None
    org = balance.org
    k = ex.k_coo(state, company.id, balance, estimate=estimate)
    pools = support_pools(state, view, balance, data) if is_scaleup(company, balance) else {}
    factors = {key: support_factor(p.coverage, k, org) for key, p in pools.items()}
    cto = ex.multiplier(state, company.id, ex.CTO, balance, estimate=estimate)
    cro = ex.multiplier(state, company.id, ex.CRO, balance, estimate=estimate)
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
        cpo=ex.multiplier(state, company.id, ex.CPO, balance, estimate=estimate),
        cmo=ex.multiplier(state, company.id, ex.CMO, balance, estimate=estimate),
        cross_division=org.cross_division_factor,
        qcap=ex.side_factor(state, company.id, ex.CTO, "qcap", balance, estimate=estimate),
        churn=ex.churn_factor(state, company.id, balance, estimate=estimate),
        brand=ex.side_factor(state, company.id, ex.CMO, "brand", balance, estimate=estimate),
        awareness=ex.side_factor(
            state, company.id, ex.CMO, "awareness", balance, estimate=estimate
        ),
        pricing=ex.side_factor(state, company.id, ex.CRO, "pricing", balance, estimate=estimate),
        pool_churn={key: support_churn(p.coverage, k, org) for key, p in pools.items()},
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


def delegate_energy_factor(
    state: GameState, view: OrgView, person_id: int, balance: Balance, data: GameData
) -> float:
    """A delegate's monthly energy x c of their pool (18.4); 1 before stage 3."""
    if not is_scaleup(state.company(view.company_id), balance):
        return 1.0
    pools = support_pools(state, view, balance, data)
    return pools[pool_of(view, person_id)].coverage
