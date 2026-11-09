"""Fabless chips (docs/formulas.md 26.3): a chip product's type, yield, unit cost, wafer
supply and what own accelerators do to GPU data centres' capex.

- **Type.** A chip product is one of the chip categories (one per `chips.types` key); its
  type is the category's `chip_type`.
- **Yield** `0.70 + 0.003 x chip-design lead`, at most `chips.chip_yield.cap` (0.95 after
  Chiplets), the lead from M11's R&D tree.
- **Unit cost** `wafer price / (chips per wafer x yield) + packaging`; the wafer price is the
  running wafer contracts' (locked at signing), else this month's index price.
- **Capacity** comes from wafer contracts (each month's wafer starts after allocation x chips
  per wafer x yield) and, from M21 (38.2), the company's own fabs (`tst.sim.fabs.supply`),
  taken first.
- **M21 (38.1, 38.3).** A contract may name a node (its price is the node's market price); the
  foundry market's capacity factor moves every contract's price and allocation (exactly 1
  through 2025 unless the player's fabs sell slots). Own-fab chips cost the fab's cost per good
  die; their wafer part is booked with the fab's month, so only packaging posts at sale.

Every function takes a `company_id` or a product; nothing assumes one player company.
"""

from __future__ import annotations

from tst.sim.chips import formulas as cf
from tst.sim.chips.config import ChipTypeDef
from tst.sim.commodities import costs
from tst.sim.data_models import Balance, CategoryDef, GameData
from tst.sim.errors import FacilityRuleError
from tst.sim.fabs import market as fm
from tst.sim.fabs import supply as fs
from tst.sim.geopolitics import supply as geo_supply
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


def _chip_type(product: Product, data: GameData) -> str:
    chip_type = data.category(product.category).chip_type
    assert chip_type is not None
    return chip_type


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
    state: GameState,
    chip_type: str,
    balance: Balance,
    data: GameData,
    foundry: str,
    node: str | None = None,
) -> float:
    """A wafer at this month's foundry_wafer index from a foundry (what a contract locks), x the
    foundry market's capacity factor (M21, 38.3); at a named node, the node's market price."""
    ch = balance.chips
    mult = ch.contract.foundries[foundry].price_mult
    if node is not None:
        return fm.node_price_cents(state, node, balance, data) * mult
    index = costs.cost_index(state, ch.good, data, balance)  # M17: x the chip mix (33.2)
    return ch.types[chip_type].wafer_cents * index * mult * fm.price_factor(state, balance, data)


def check_node_contract(
    state: GameState, foundry: str, node: str, balance: Balance, data: GameData
) -> None:
    """M21 (38.3): a contract at a node needs a rival foundry backing `foundry` that runs it."""
    if data.nodes is None or node not in data.nodes.node_keys():
        raise FacilityRuleError(f"unknown node {node!r}")
    backing = [f for f in data.nodes.foundries if f.contract == foundry]
    tl = fm.timeline(state, balance, data)
    if not any(tl.foundry_has(f.key, node, state.turn) for f in backing):
        label = balance.chips.contract.foundries[foundry].label
        raise FacilityRuleError(f"{label} does not run that node yet")


def own_wafers(state: GameState, product_id: int) -> tuple[float, float, float]:
    """M20 (36.2): this month's own-group wafers for the product's wafer starts: (wafers, mean
    transfer price, market wafer price), in cents. (0, 0, 0) without a wafer plant."""
    lots = [s for s in state.own_supply if s.product_id == product_id and s.turn == state.turn]
    volume = sum(s.volume for s in lots)
    if volume <= 0:
        return 0.0, 0.0, 0.0
    price = sum(s.volume * s.unit_cents for s in lots) / volume
    return volume, price, lots[0].market_cents


def own_wafer_share(state: GameState, product_id: int) -> float:
    """The share of the product's wafer starts on the group's own wafers (36.2)."""
    volume = own_wafers(state, product_id)[0]
    if volume <= 0:
        return 0.0
    starts = sum(c.units for c in wafer_contracts(state, product_id))
    return min(1.0, volume / starts) if starts > 0 else 0.0


def wafer_cents(state: GameState, product: Product, balance: Balance, data: GameData) -> float:
    """The product's wafer price: its running contracts' locked prices weighted by wafer
    starts, else this month's price at the first foundry. M20 (36.2): the share of starts on
    the group's own wafers pays the group's wafer price for the substrate instead of the
    market's (a fabless company without a wafer plant pays exactly what it did)."""
    contracts = wafer_contracts(state, product.id)
    wafers = sum(c.units for c in contracts)
    if wafers:
        price = sum(c.units * c.price_cents for c in contracts) / wafers
        share = own_wafer_share(state, product.id)
        if share > 0:
            _, own, market = own_wafers(state, product.id)
            price -= share * (market - own)
        return price
    chip_type = data.category(product.category).chip_type
    assert chip_type is not None
    first = next(iter(balance.chips.contract.foundries))
    return index_wafer_cents(state, chip_type, balance, data, first)


def contract_unit_cents(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> float:
    """A chip from wafer contracts: wafer price / (chips per wafer x yield) + packaging (26.3)."""
    t = type_of(product, data, balance)
    y = chip_yield(state, product.company_id, balance, data)
    wafer = wafer_cents(state, product, balance, data)
    # M22 (39.3): the premium on the wafer's commodities bought from a restricting actor
    wafer += geo_supply.surcharge_cents(
        state, product.company_id, balance.chips.good, t.wafer_cents, balance, data
    )
    return cf.chip_unit_cents(wafer, t.per_wafer, y, balance.chips.packaging_cents)


def fab_unit_cents(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> float | None:
    """M21 (38.2): a chip from the company's own fabs at their cost per good die (last month's
    cost a start, by starts); None without fab chips or before a fab's first month."""
    shares = [s for s in fs.product_shares(state, product, balance, data) if s.starts > 0]
    if not shares:
        return None
    starts = sum(s.starts for s in shares)
    chips_ = sum(s.starts * s.chips_per_start for s in shares)
    cost = sum(s.starts * s.cost_per_start_cents for s in shares)
    if chips_ <= 0 or cost <= 0:
        return None
    return cost / starts / (chips_ / starts) + balance.chips.packaging_cents


def fab_share_of_capacity(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> float:
    """The share of the product's chips this month that its own fabs can make (38.2)."""
    own = fs.fab_chips(state, product, balance, data)
    if own <= 0:
        return 0.0
    total = contract_capacity(state, product, balance, data) + own
    return own / total if total > 0 else 0.0


def unit_cost_cents(state: GameState, product: Product, balance: Balance, data: GameData) -> float:
    """wafer price / (chips per wafer x yield) + packaging (26.3); with own fabs (M21, 38.2),
    the blend of the fab's cost per good die and the contracts' unit cost by capacity."""
    contract = contract_unit_cents(state, product, balance, data)
    if not state.fabs:
        return contract
    own = fab_unit_cents(state, product, balance, data)
    if own is None:
        return contract
    share = fab_share_of_capacity(state, product, balance, data)
    return share * own + (1 - share) * contract


def posted_unit_cents(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> float:
    """What a chip posts to cost of goods at sale (M21): an own-fab chip's wafer part is booked
    with the fab's month, so it posts packaging only; a contract chip its unit cost."""
    contract = contract_unit_cents(state, product, balance, data)
    if not state.fabs:
        return contract
    share = fab_share_of_capacity(state, product, balance, data)
    return share * balance.chips.packaging_cents + (1 - share) * contract


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
    if share < 1 or state.turn > _HISTORY_END or state.fabs:  # M21 (38.3): rivals' capacity
        share = min(1.0, share * fm.allocation_factor(state, balance, data))
    own = own_wafer_share(state, contract.product_id)  # M20 (36.2): own wafers keep 100%
    if own > 0:
        share = own + (1 - own) * share
    # M22 (39.3): HBM controls on the maker's country, and the entity list
    share *= geo_supply.wafer_share(
        state, product.company_id, _chip_type(product, data), contract.supplier, balance, data
    )
    return contract.units * share


_HISTORY_END = fm.HISTORY_END


def contract_capacity(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> float:
    """Good chips from wafer contracts: wafer starts delivered x chips per wafer x yield (26.3)."""
    t = type_of(product, data, balance)
    y = chip_yield(state, product.company_id, balance, data)
    wafers = sum(
        wafers_delivered(state, c, balance, data) for c in wafer_contracts(state, product.id)
    )
    return cf.chips_from_wafers(wafers, t.per_wafer, y)


def chip_capacity(state: GameState, product: Product, balance: Balance, data: GameData) -> float:
    """Good chips the product can have this month: its contracts' and, from M21, its own fabs'
    (26.3, 38.2)."""
    cap = contract_capacity(state, product, balance, data)
    if state.fabs:
        cap += fs.fab_chips(state, product, balance, data)
    return cap


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
