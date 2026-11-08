"""Hardware and chip actions (ADR-0014, docs/formulas.md 26.2-26.3, M12b): sign a
contract-manufacturing contract or a wafer contract for a product, and start selling spare
assembly-plant capacity as contract manufacturing. Building a plant is M12a's
`build_facility` with the `assembly_plant` kind. They take effect at once and spend the
actor's energy.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.chips import chips
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import FacilityRuleError, ProductRuleError
from tst.sim.facilities.models import Facility
from tst.sim.hardware import cm_market
from tst.sim.hardware import formulas as hf
from tst.sim.hardware.models import ProductionContract
from tst.sim.log import inbox_item
from tst.sim.money import format_money, to_millicents
from tst.sim.products.formulas import held_feature_points
from tst.sim.products.models import Product, ProductSegment
from tst.sim.state import (
    GameState,
    with_product,
    with_product_segment,
    with_production_contract,
)

CM_SUFFIX = " Manufacturing"  # the contract-manufacturing product's name


@dataclass(frozen=True, slots=True)
class SignManufacturingContract:
    actor_id: int
    product_id: int  # a device or server product
    manufacturer: str  # hardware.contract.manufacturers key
    city: str  # cities.yaml key where it is made (Shenzhen is cheapest)
    units: int  # a month
    months: int
    kind: Literal["sign_manufacturing_contract"] = "sign_manufacturing_contract"


@dataclass(frozen=True, slots=True)
class SignWaferContract:
    actor_id: int
    product_id: int  # a chip product
    foundry: str  # chips.contract.foundries key
    wafers: int  # wafer starts a month
    months: int
    kind: Literal["sign_wafer_contract"] = "sign_wafer_contract"


@dataclass(frozen=True, slots=True)
class SellPlantCapacity:
    actor_id: int
    kind: Literal["sell_plant_capacity"] = "sell_plant_capacity"


type HardwareAction = SignManufacturingContract | SignWaferContract | SellPlantCapacity


def _own_product(state: GameState, company: int, product_id: int) -> Product:
    product = state.product(product_id)
    if product is None or product.company_id != company or product.status == "retired":
        raise ProductRuleError(f"no product {product_id}")
    return product


def _months(months: int, lo: float, hi: float) -> None:
    if not lo <= months <= hi:
        raise FacilityRuleError(f"a contract runs {lo:g} to {hi:g} months")


def manufacturing_fee_cents(balance: Balance, category: str, manufacturer: str, city: str) -> float:
    """The fee a unit (26.2): the category's base fee x the manufacturer's x the city's
    (Shenzhen 1, elsewhere `city_fee_mult`)."""
    c = balance.hardware.contract
    base = balance.hardware.bom[category].contract_fee_cents
    city_mult = 1.0 if city == c.cheap_city else c.city_fee_mult
    return hf.contract_fee_cents(base, c.manufacturers[manufacturer].fee_mult, city_mult)


def sign_manufacturing_contract(
    state: GameState, action: SignManufacturingContract, balance: Balance, data: GameData
) -> Outcome:
    """Immediate, energy 6: `units` a month for 12-24 months at a fee a unit; take-or-pay
    charges 50% of the fee on unused volume each month (26.2)."""
    company = acting_company(state, action.actor_id)
    product = _own_product(state, company, action.product_id)
    c = balance.hardware.contract
    if product.category not in balance.hardware.bom:
        raise ProductRuleError(f"{product.name} is not a device or server")
    if action.manufacturer not in c.manufacturers:
        raise FacilityRuleError(f"unknown contract manufacturer {action.manufacturer!r}")
    if data.cities and not data.has_city(action.city):
        raise FacilityRuleError(f"unknown city {action.city!r}")
    _months(action.months, c.months.lo, c.months.hi)
    if not 0 < action.units <= c.max_units:
        raise FacilityRuleError(f"a contract covers 1 to {c.max_units:,} units a month")
    state = spend_energy(
        state, action.actor_id, "sign_manufacturing_contract", balance, cost=c.energy
    )
    fee = manufacturing_fee_cents(balance, product.category, action.manufacturer, action.city)
    contract_id, ids = state.next_ids.take("production_contract")
    contract = ProductionContract(
        id=contract_id,
        company_id=company,
        product_id=product.id,
        kind="assembly",
        supplier=action.manufacturer,
        units=action.units,
        price_millicents=to_millicents(fee),
        signed_turn=state.turn,
        end_turn=state.turn + action.months - 1,
        city=action.city,
    )
    state = with_production_contract(replace(state, next_ids=ids), contract)
    log = inbox_item(
        state.turn,
        company,
        "production_contract_signed",
        what="Contract-manufacturing",
        product=product.name,
        supplier=c.manufacturers[action.manufacturer].label,
        units=f"{action.units:,} units",
        months=action.months,
        price=f"{format_money(round(fee))} a unit",
        take_or_pay=f"{c.take_or_pay:.0%}",
    )
    return Outcome(state, (), (log,))


def sign_wafer_contract(
    state: GameState, action: SignWaferContract, balance: Balance, data: GameData
) -> Outcome:
    """Immediate, energy 6: wafer starts a month from a foundry at this month's wafer price,
    locked for 12-36 months (26.3, as 22.4); unused starts are charged take-or-pay."""
    company = acting_company(state, action.actor_id)
    product = _own_product(state, company, action.product_id)
    w = balance.chips.contract
    chip_type = data.category(product.category).chip_type
    if chip_type is None:
        raise ProductRuleError(f"{product.name} is not a chip")
    if action.foundry not in w.foundries:
        raise FacilityRuleError(f"unknown foundry {action.foundry!r}")
    _months(action.months, w.months.lo, w.months.hi)
    if not 0 < action.wafers <= w.max_wafers:
        raise FacilityRuleError(f"a contract covers 1 to {w.max_wafers:,} wafers a month")
    state = spend_energy(state, action.actor_id, "sign_wafer_contract", balance, cost=w.energy)
    price = chips.index_wafer_cents(state, chip_type, balance, data, action.foundry)
    contract_id, ids = state.next_ids.take("production_contract")
    contract = ProductionContract(
        id=contract_id,
        company_id=company,
        product_id=product.id,
        kind="wafer",
        supplier=action.foundry,
        units=action.wafers,
        price_millicents=to_millicents(price),
        signed_turn=state.turn,
        end_turn=state.turn + action.months - 1,
    )
    state = with_production_contract(replace(state, next_ids=ids), contract)
    log = inbox_item(
        state.turn,
        company,
        "production_contract_signed",
        what="Wafer",
        product=product.name,
        supplier=w.foundries[action.foundry].label,
        units=f"{action.wafers:,} wafer starts",
        months=action.months,
        price=f"{format_money(round(price))} a wafer",
        take_or_pay=f"{w.take_or_pay:.0%}",
    )
    return Outcome(state, (), (log,))


def _plants(state: GameState, company: int, balance: Balance) -> list[Facility]:
    return [f for f in state.company_facilities(company) if f.kind == balance.hardware.plant_kind]


def sell_plant_capacity(
    state: GameState, action: SellPlantCapacity, balance: Balance, data: GameData
) -> Outcome:
    """Immediate, energy as create_product: a live contract-manufacturing product that sells
    the company's spare plant capacity (26.2), at reference prices. Needs a plant (building
    or live) and no such product yet."""
    company = acting_company(state, action.actor_id)
    if not _plants(state, company, balance):
        raise FacilityRuleError("build an assembly plant before selling its capacity")
    if cm_market.cm_product(state, company, balance) is not None:
        raise FacilityRuleError("the company already sells its spare plant capacity")
    category = data.category(balance.hardware.capacity_category)
    state = spend_energy(state, action.actor_id, "create_product", balance)
    product_id, ids = state.next_ids.take("product")
    quality = cm_market.plant_quality(state, company, balance)
    c = balance.compute
    features = c.feature_base
    product = Product(
        id=product_id,
        company_id=company,
        category=category.key,
        name=(state.company(company).name + CM_SUFFIX)[:80],  # tunable-exempt: name width
        status="live",
        quality=quality if quality is not None else balance.products.start_quality,
        feature_points=held_feature_points(features, category, state.turn),
        brand=0.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
    )
    state = replace(with_product(state, product), next_ids=ids)
    for market in category.markets:
        state = with_product_segment(
            state,
            ProductSegment(
                product_id, market.segment, market.reference_price_cents, added_turn=state.turn
            ),
        )
    log = inbox_item(state.turn, company, "cm_started", product=product.name)
    return Outcome(state, (), (log,))
