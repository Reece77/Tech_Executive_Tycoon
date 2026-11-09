"""Fabless chips (docs/formulas.md 26.3): a chip product's type, yield, unit cost, wafer
supply and what own accelerators do to GPU data centres' capex.

- **Type.** A chip product is one of the chip categories (one per `chips.types` key); its
  type is the category's `chip_type`.
- **Yield** `0.70 + 0.003 x chip-design lead`, at most `chips.chip_yield.cap` (0.95 after
  Chiplets), the lead from M11's R&D tree.
- **Unit cost** `wafer price / (chips per wafer x yield) + packaging`; the wafer price is the
  running wafer contracts' (locked at signing), else this month's index price.
- **Capacity** comes only from wafer contracts: each month's wafer starts after allocation x
  chips per wafer x yield.

Every function takes a `company_id` or a product; nothing assumes one player company.
"""

from __future__ import annotations

from tst.sim.chips import formulas as cf
from tst.sim.chips.config import ChipTypeDef
from tst.sim.commodities import costs
from tst.sim.data_models import Balance, CategoryDef, GameData
from tst.sim.hardware.models import ProductionContract
from tst.sim.hardware.supply import delivered_share
from tst.sim.products.models import Product
from tst.sim.research import levels
from tst.sim.state import GameState


def chip_category(data: GameData, chip_type: str) -> CategoryDef:
    for c in data.categories:
        if c.chip_type == chip_type:
            return c
    raise KeyError(chip_type)


def is_chip(product: Product, data: GameData) -> bool:
    return data.category(product.category).chip_type is not None


def type_of(product: Product, data: GameData, balance: Balance) -> ChipTypeDef:
    chip_type = data.category(product.category).chip_type
    assert chip_type is not None
    return balance.chips.types[chip_type]


def market_price_cents(data: GameData, balance: Balance, chip_type: str, segment: str) -> int:
    """A chip type's market price: its category's reference price in `segment` (26.2)."""
    return chip_category(data, chip_type).market(segment).reference_price_cents


def bought_price_cents(data: GameData, balance: Balance, chip_type: str) -> int:
    """What a device maker pays for a bought chip: the device OEM reference price (26.2)."""
    return market_price_cents(data, balance, chip_type, balance.chips.price_segment)


def chip_yield(state: GameState, company_id: int, balance: Balance, data: GameData) -> float:
    """0.70 + 0.003 x the company's chip-design lead, at most the cap (26.3, 26.4)."""
    y = balance.chips.chip_yield
    lead = levels.lead(state, company_id, y.domain)
    return cf.chip_yield(y.base, y.per_lead, lead, levels.yield_cap(state, data, y.cap))


def wafer_contracts(state: GameState, product_id: int) -> list[ProductionContract]:
    return [
        c
        for c in state.production_contracts
        if c.product_id == product_id and c.kind == "wafer" and c.running(state.turn)
    ]


def index_wafer_cents(
    state: GameState, chip_type: str, balance: Balance, data: GameData, foundry: str
) -> float:
    """A wafer at this month's foundry_wafer index from a foundry (what a contract locks)."""
    ch = balance.chips
    index = costs.cost_index(state, ch.good, data, balance)  # M17: x the chip mix (33.2)
    return ch.types[chip_type].wafer_cents * index * ch.contract.foundries[foundry].price_mult


def wafer_cents(state: GameState, product: Product, balance: Balance, data: GameData) -> float:
    """The product's wafer price: its running contracts' locked prices weighted by wafer
    starts, else this month's price at the first foundry."""
    contracts = wafer_contracts(state, product.id)
    wafers = sum(c.units for c in contracts)
    if wafers:
        return sum(c.units * c.price_cents for c in contracts) / wafers
    chip_type = data.category(product.category).chip_type
    assert chip_type is not None
    first = next(iter(balance.chips.contract.foundries))
    return index_wafer_cents(state, chip_type, balance, data, first)


def unit_cost_cents(state: GameState, product: Product, balance: Balance, data: GameData) -> float:
    """wafer price / (chips per wafer x yield) + packaging (26.3)."""
    t = type_of(product, data, balance)
    y = chip_yield(state, product.company_id, balance, data)
    return cf.chip_unit_cents(
        wafer_cents(state, product, balance, data), t.per_wafer, y, balance.chips.packaging_cents
    )


def wafers_delivered(
    state: GameState, contract: ProductionContract, balance: Balance, data: GameData
) -> float:
    """A wafer contract's starts this month after allocation (26.3)."""
    product = state.product(contract.product_id)
    assert product is not None
    t = type_of(product, data, balance)
    share = delivered_share(
        state, balance.chips.good, contract.signed_turn, data, advanced=t.advanced_node
    )
    return contract.units * share


def chip_capacity(state: GameState, product: Product, balance: Balance, data: GameData) -> float:
    """Good chips the product can have this month: wafer starts delivered x chips per wafer x
    yield (26.3)."""
    t = type_of(product, data, balance)
    y = chip_yield(state, product.company_id, balance, data)
    wafers = sum(
        wafers_delivered(state, c, balance, data) for c in wafer_contracts(state, product.id)
    )
    return cf.chips_from_wafers(wafers, t.per_wafer, y)


def own_chip_product(
    state: GameState, company_id: int, chip_type: str, data: GameData
) -> Product | None:
    """The company's first live chip product of a type (by id), if any."""
    for p in state.company_products(company_id):
        if p.status == "live" and data.category(p.category).chip_type == chip_type:
            return p
    return None


def gpu_capex_factor(state: GameState, company_id: int, balance: Balance, data: GameData) -> float:
    """Own GPU data centres with the company's own accelerator: capex x (0.4 + 0.6 x own unit
    cost / market chip price) (26.3); 1 without one."""
    g = balance.chips.gpu_capex
    product = own_chip_product(state, company_id, g.chip_type, data)
    if product is None:
        return 1.0
    own = unit_cost_cents(state, product, balance, data)
    market = market_price_cents(data, balance, g.chip_type, g.segment)
    return cf.gpu_capex_factor(own, market, g.floor, g.share)
