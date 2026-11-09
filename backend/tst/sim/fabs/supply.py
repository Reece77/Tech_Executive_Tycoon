"""Own fabs supply the company's chips (docs/formulas.md 38.2 with 26.3).

Each month a live fab's available starts (`FabMonth.available`, set in phase 4) are shared
among its company's selling chip products: in proportion to what each needed last month
(chips sold, used inside and lost, in starts), equally when none has a month yet. A product's
chips from a fab are `starts x chips per wafer x its design yield x min(1, fab yield / mature
yield)`. Production takes fab chips before wafer contracts' (38.2: "the group's own chips
first"); starts a product does not use are sold as foundry slots (`plants.settle_fabs`).

Fabs supply chips of their own company only (M21 decision; a group transfer is a follow-up).
Nothing here runs for a company without a live fab.
"""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.data_models import Balance, GameData
from tst.sim.fabs.models import Fab
from tst.sim.products.models import SELLING, Product
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class FabShare:
    facility_id: int
    node: str
    starts: float
    chips_per_start: float  # good chips a start makes for this product
    cost_per_start_cents: float  # the fab's full cost a start (last month's, else 0)


def live_fabs(state: GameState, company_id: int) -> list[Fab]:
    return [
        f
        for f in state.fabs
        if f.company_id == company_id
        and f.month is not None
        and f.month.turn == state.turn
        and f.month.available > 0
    ]


def chip_products(state: GameState, company_id: int, data: GameData) -> list[Product]:
    return [
        p
        for p in state.company_products(company_id)
        if p.status in SELLING and data.category(p.category).chip_type is not None
    ]


def _per_start(
    state: GameState, product: Product, fab: Fab, balance: Balance, data: GameData
) -> float:
    from tst.sim.chips import chips  # chips imports this module

    t = chips.type_of(product, data, balance)
    y = chips.chip_yield(state, product.company_id, balance, data)
    return t.per_wafer * y * min(1.0, fab.yield_ / balance.fab.yield_.mature)


def _wish(state: GameState, product_id: int) -> float:
    """Chips the product needed last month (sold, used inside and lost)."""
    for row in state.production:
        if row.product_id == product_id:
            return row.units + row.internal_units + row.lost_units
    return 0.0


def allocation(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> dict[int, list[FabShare]]:
    """Product id -> its shares of the company's live fabs this month."""
    fabs = live_fabs(state, company_id)
    if not fabs:
        return {}
    products = chip_products(state, company_id, data)
    if not products:
        return {}
    out: dict[int, list[FabShare]] = {p.id: [] for p in products}
    for fab in fabs:
        assert fab.month is not None
        per = {p.id: _per_start(state, p, fab, balance, data) for p in products}
        wish = {p.id: _wish(state, p.id) / per[p.id] if per[p.id] > 0 else 0.0 for p in products}
        total = sum(wish.values())
        prev = fab.history[-1][3] if fab.history else 0.0
        for p in products:
            share = wish[p.id] / total if total > 0 else 1 / len(products)
            out[p.id].append(
                FabShare(fab.facility_id, fab.node, fab.month.available * share, per[p.id], prev)
            )
    return out


def product_shares(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> list[FabShare]:
    if not state.fabs:
        return []
    return allocation(state, product.company_id, balance, data).get(product.id, [])


def fab_chips(state: GameState, product: Product, balance: Balance, data: GameData) -> float:
    return sum(s.starts * s.chips_per_start for s in product_shares(state, product, balance, data))


def product_node(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> str | None:
    """The node a product's chips are made on this month: its largest fab share's, else its
    running wafer contracts' newest (38.4); None (the category's median) otherwise."""
    shares = product_shares(state, product, balance, data)
    if shares:
        return max(shares, key=lambda s: s.starts).node
    from tst.sim.chips import chips

    nodes = [c.node for c in chips.wafer_contracts(state, product.id) if c.node is not None]
    if not nodes or data.nodes is None:
        return None
    keys = data.nodes.node_keys()
    return max(nodes, key=keys.index)
