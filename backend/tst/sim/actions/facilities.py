"""Facility actions (ADR-0014, docs/formulas.md 22, M12a): build a data centre, close or sell
one, assign the unit that staffs it, sign a component contract, and start selling spare
capacity as Cloud hosting. They take effect at once and spend the actor's energy.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.actions.org import active_unit
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import FacilityRuleError, InsufficientCashError, UnknownFacilityError
from tst.sim.facilities import compute, goods, lifecycle
from tst.sim.facilities import formulas as ff
from tst.sim.facilities.models import Facility, SupplyContract
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.log import inbox_item
from tst.sim.products.formulas import held_feature_points
from tst.sim.products.models import Product, ProductSegment
from tst.sim.state import (
    GameState,
    with_contract,
    with_facility,
    with_product,
    with_product_segment,
)

CLOUD_SUFFIX = " Cloud"  # the Cloud hosting product's name: "<company> Cloud"


@dataclass(frozen=True, slots=True)
class BuildFacility:
    actor_id: int
    facility_kind: str  # balance.facility.kinds key
    region: str
    capacity: int
    contract_id: int | None = None
    city: str | None = None  # M12b (26.2): a cities.yaml key in `region` (a plant's city)
    kind: Literal["build_facility"] = "build_facility"


@dataclass(frozen=True, slots=True)
class SellFacility:
    actor_id: int
    facility_id: int
    kind: Literal["sell_facility"] = "sell_facility"


@dataclass(frozen=True, slots=True)
class StaffFacility:
    actor_id: int
    facility_id: int
    unit_id: int | None  # None = nobody
    kind: Literal["staff_facility"] = "staff_facility"


@dataclass(frozen=True, slots=True)
class SignContract:
    actor_id: int
    good: str  # components_history.yaml key
    months: int
    volume: int  # capacity units of builds
    kind: Literal["sign_contract"] = "sign_contract"


@dataclass(frozen=True, slots=True)
class SellCapacity:
    actor_id: int
    kind: Literal["sell_capacity"] = "sell_capacity"


type FacilityAction = BuildFacility | SellFacility | StaffFacility | SignContract | SellCapacity


def own_facility(state: GameState, company_id: int, facility_id: int) -> Facility:
    facility = state.facility(facility_id)
    if facility is None or facility.company_id != company_id or facility.status == "closed":
        raise UnknownFacilityError(f"no facility {facility_id}")
    return facility


def build_facility(
    state: GameState,
    action: BuildFacility,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    """Immediate, energy 12: order a build of 100, 500, 2,000 or 10,000 units in a region
    (22.2). Capex is paid in equal parts while it is built; the first part needs cash now."""
    company = acting_company(state, action.actor_id)
    fb = balance.facility
    if action.facility_kind not in fb.kinds:
        raise FacilityRuleError(f"unknown facility kind {action.facility_kind!r}")
    if action.region not in data.region_keys:
        raise FacilityRuleError(f"unknown region {action.region!r}")
    if action.facility_kind in balance.refining.kinds:  # M20: refineries have their own action
        raise FacilityRuleError("order a refinery with build_refinery")
    kind = fb.kinds[action.facility_kind]
    allowed = kind.sizes or fb.sizes  # M12b: plants have their own sizes
    if action.capacity not in allowed:
        sizes = ", ".join(f"{s:,}" for s in allowed)
        raise FacilityRuleError(f"a {kind.label.lower()} has {sizes} {kind.unit}")
    if action.city is not None and (
        not data.has_city(action.city) or data.city(action.city).region != action.region
    ):
        raise FacilityRuleError(f"{action.city!r} is not a city in that region")
    if action.contract_id is not None and (
        lifecycle.usable_contract(state, company, kind.input_good, action.contract_id) is None
    ):
        raise FacilityRuleError(f"contract {action.contract_id} cannot be used for this build")
    q = lifecycle.quote(
        state,
        company,
        action.facility_kind,
        action.region,
        action.capacity,
        balance,
        data,
        action.contract_id,
    )
    if account_balance(balances, company, CASH) < q.monthly_capex_cents:
        raise InsufficientCashError(f"the first capex payment needs {q.monthly_capex_cents} cents")
    state = spend_energy(state, action.actor_id, "build_facility", balance, cost=fb.build_energy)
    state, facility = lifecycle.order_build(state, company, q)
    if action.city is not None:  # M12b (26.2): its city's hires get the city's talent
        facility = replace(facility, city=action.city)
        state = with_facility(state, facility)
    name = lifecycle.facility_name(facility, balance, data)
    later = (
        f" Components are short: {q.late:,} {kind.unit} arrive {q.late_months} months late."
        if q.late
        else ""
    )
    log = inbox_item(
        state.turn,
        company,
        "facility_ordered",
        facility=name,
        units=f"{q.capacity:,} {kind.unit}",
        region=data.region(action.region).label,
        capex_cents=q.capex_cents,
        months=q.build_months,
        ready=format_turn(facility.ready_turn),
        later=later,
        staff=q.staff_needed,
    )
    return Outcome(state, (), (log,))


def sell_facility(
    state: GameState, action: SellFacility, balance: Balance, data: GameData
) -> Outcome:
    """Immediate, energy 12: sell for half its book value (22.2)."""
    company = acting_company(state, action.actor_id)
    facility = own_facility(state, company, action.facility_id)
    if not balance.facility.kinds[facility.kind].generic:
        raise FacilityRuleError("close or sell a mine from the Mines screen")
    state = spend_energy(
        state, action.actor_id, "sell_facility", balance, cost=balance.facility.close_energy
    )
    book = facility.book_value_cents
    state, entry, proceeds = lifecycle.sell(state, facility, balance, data)
    log = inbox_item(
        state.turn,
        company,
        "facility_sold",
        facility=lifecycle.facility_name(facility, balance, data),
        proceeds_cents=proceeds,
        book_cents=book,
    )
    return Outcome(state, (entry,) if entry else (), (log,))


def staff_facility(state: GameState, action: StaffFacility, balance: Balance) -> Outcome:
    """Immediate, energy 2: the unit whose infrastructure people staff it (22.2). A unit
    staffs at most one facility."""
    company = acting_company(state, action.actor_id)
    facility = own_facility(state, company, action.facility_id)
    if action.unit_id is not None:
        active_unit(state, company, action.unit_id)
        other = next(
            (f for f in state.company_facilities(company) if f.unit_id == action.unit_id),
            None,
        )
        if other is not None and other.id != facility.id:
            raise FacilityRuleError("that unit already staffs another data centre")
    if facility.unit_id == action.unit_id:
        raise FacilityRuleError("that unit already staffs it")
    state = spend_energy(
        state, action.actor_id, "staff_facility", balance, cost=balance.facility.assign_energy
    )
    return Outcome(with_facility(state, replace(facility, unit_id=action.unit_id)))


def sign_contract(
    state: GameState, action: SignContract, balance: Balance, data: GameData
) -> Outcome:
    """Immediate, energy 6: lock a component's index for 12-36 months on a volume of builds
    (22.4). Contracted builds get full allocation; unused volume is charged take-or-pay."""
    company = acting_company(state, action.actor_id)
    sb = balance.supply
    if data.components is None or action.good not in {g.key for g in data.components.goods}:
        raise FacilityRuleError(f"unknown component {action.good!r}")
    if not sb.contract_months.lo <= action.months <= sb.contract_months.hi:
        raise FacilityRuleError(
            f"a contract runs {sb.contract_months.lo:g} to {sb.contract_months.hi:g} months"
        )
    if action.volume <= 0:
        raise FacilityRuleError("a contract needs a volume")
    kind = next((k for k in balance.facility.kinds.values() if k.input_good == action.good), None)
    if kind is None:
        raise FacilityRuleError(f"no facility is built from {action.good!r}")
    state = spend_energy(state, action.actor_id, "sign_contract", balance, cost=sb.contract_energy)
    index = goods.index_now(state, action.good, data)
    contract_id, ids = state.next_ids.take("contract")
    contract = SupplyContract(
        id=contract_id,
        company_id=company,
        good=action.good,
        index=index,
        signed_turn=state.turn,
        end_turn=state.turn + action.months - 1,
        volume=action.volume,
        unit_value_cents=ff.capex_cents(1, kind.capex_per_unit_cents, index),
    )
    state = with_contract(replace(state, next_ids=ids), contract)
    log = inbox_item(
        state.turn,
        company,
        "contract_signed",
        good=data.components.good(action.good).label,
        units=f"{action.volume:,} {kind.unit}",
        index=f"{index:.2f}",
        end=format_turn(contract.end_turn),
        take_or_pay=f"{sb.take_or_pay:.0%}",
    )
    return Outcome(state, (), (log,))


def sell_capacity(
    state: GameState, action: SellCapacity, balance: Balance, data: GameData
) -> Outcome:
    """Immediate, energy as create_product: a live Cloud hosting product that sells the
    company's spare capacity (22.3), priced at the reference price in every segment. Needs a
    data centre (building or live) and no Cloud hosting product yet."""
    company = acting_company(state, action.actor_id)
    if not any(compute.is_compute(f, balance) for f in state.company_facilities(company)):
        raise FacilityRuleError("build a data centre before selling capacity")
    if compute.capacity_product(state, company, data) is not None:
        raise FacilityRuleError("the company already sells its spare capacity")
    category = data.category(balance.compute.capacity_category)
    state = spend_energy(state, action.actor_id, "create_product", balance)
    product_id, ids = state.next_ids.take("product")
    rel = lifecycle.mean_reliability(state, company, balance)
    c = balance.compute
    features = ff.feature_target(0.0, c.feature_base, c.feature_per_lead)
    product = Product(
        id=product_id,
        company_id=company,
        category=category.key,
        name=(state.company(company).name + CLOUD_SUFFIX)[:80],  # tunable-exempt: name width
        status="live",
        quality=rel if rel is not None else balance.products.start_quality,
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
    log = inbox_item(state.turn, company, "cloud_started", product=product.name)
    return Outcome(state, (), (log,))
