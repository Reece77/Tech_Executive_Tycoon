"""Own fabs supply the company's chips (docs/formulas.md 38.2 with 26.3).

Each month a live fab's available starts (`FabMonth.available`, set in phase 4) are shared
among its company's selling chip products: in proportion to what each needed last month
(chips sold, used inside and lost, in starts), equally when none has a month yet. A product's
chips from a fab are `starts x chips per wafer x its design yield x min(1, fab yield / mature
yield)`. Production takes fab chips before wafer contracts' (38.2: "the group's own chips
first"); starts a product does not use are sold as foundry slots (`plants.settle_fabs`).

M23a (ADR-0020 1, 31.6): a fab supplies the chip products of **any company of its group**, its
own company's and its sister companies' alike; a sister company pays for the starts it used at
the `chips` flow's transfer price between the two (cost by default: the fab's cost a start; else
cost plus or the node's market price), settled with the fab's month (`plants.settle_fabs`).
Nothing here runs for a company without a live fab in its group.
"""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.data_models import Balance, GameData
from tst.sim.fabs.models import Fab
from tst.sim.products.models import SELLING, Product
from tst.sim.state import GameState

COST = 3  # tunable-exempt: the cost a start's place in a fab's history row
FLOW_GOOD = "chips"  # M16's flow good for chips (31.6)


@dataclass(frozen=True, slots=True)
class FabShare:
    facility_id: int
    node: str
    starts: float
    chips_per_start: float  # good chips a start makes for this product
    cost_per_start_cents: float  # the fab's full cost a start (last month's, else 0)


def _group(state: GameState, company_id: int) -> tuple[int, ...]:
    from tst.sim.refining.plants import group_of

    return group_of(state, company_id)


def live_fabs(state: GameState, company_id: int) -> list[Fab]:
    """The live fabs of `company_id`'s group (M23a), in facility order."""
    group = _group(state, company_id)
    return [
        f
        for f in state.fabs
        if f.company_id in group
        and f.month is not None
        and f.month.turn == state.turn
        and f.month.available > 0
    ]


def chip_products(state: GameState, company_id: int, data: GameData) -> list[Product]:
    """The selling chip products of `company_id`'s group (M23a), by company then product."""
    return [
        p
        for cid in _group(state, company_id)
        for p in state.company_products(cid)
        if p.status in SELLING and data.category(p.category).chip_type is not None
    ]


def start_price_cents(
    state: GameState, fab: Fab, buyer: int, cost: float, balance: Balance, data: GameData
) -> float:
    """What a start costs company `buyer` (31.6): the fab's cost inside its own company, else
    the `chips` flow's transfer price between the two (cost when none is set) against the node's
    market wafer price."""
    if buyer == fab.company_id:
        return cost
    from tst.sim.fabs import market as fm
    from tst.sim.group import formulas as gf
    from tst.sim.group.transfer import flow_of

    flow = flow_of(state, fab.company_id, buyer, FLOW_GOOD)
    if flow is None:
        return cost
    market = fm.node_price_cents(state, fab.node, balance, data)
    return float(
        gf.transfer_price_cents(flow.kind, round(cost), round(market), balance, flow.margin)
    )


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
        prev = fab.history[-1][COST] if fab.history else 0.0
        for p in products:
            share = wish[p.id] / total if total > 0 else 1 / len(products)
            price = start_price_cents(state, fab, p.company_id, prev, balance, data)
            out[p.id].append(
                FabShare(fab.facility_id, fab.node, fab.month.available * share, per[p.id], price)
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
