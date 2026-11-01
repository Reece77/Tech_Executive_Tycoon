"""Geography actions (ADR-0014, docs/formulas.md 19, M9): leasing and closing offices, the
office a unit works from, launching a product in a region and its prices there."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.actions.org import active_unit
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import GeoRuleError, InsufficientCashError, UnknownCityError
from tst.sim.geo import formulas as gf
from tst.sim.geo.cities import home_region, hq_city, settle_home_cities
from tst.sim.geo.models import Office, ProductRegion, RegionalSegment
from tst.sim.ledger import (
    CASH,
    RENT,
    RESEARCH,
    LedgerBalances,
    LedgerEntry,
    LedgerLine,
    account_balance,
)
from tst.sim.log import inbox_item
from tst.sim.state import (
    GameState,
    with_office,
    with_product_region,
    with_regional_segment,
    with_unit,
)


@dataclass(frozen=True, slots=True)
class LeaseOffice:
    actor_id: int
    city: str
    seats: int
    kind: Literal["lease_office"] = "lease_office"


@dataclass(frozen=True, slots=True)
class CloseOffice:
    actor_id: int
    office_id: int
    kind: Literal["close_office"] = "close_office"


@dataclass(frozen=True, slots=True)
class SetUnitOffice:
    actor_id: int
    unit_id: int
    office_id: int | None  # None = the parent's office, up to flexible space in the HQ city
    kind: Literal["set_unit_office"] = "set_unit_office"


def office_rent_cents(office: Office, balance: Balance, data: GameData) -> int:
    """An office's monthly rent (19.2)."""
    return gf.lease_rent_cents(office.seats, data.city(office.city).rent_index, balance)


def open_office(state: GameState, company_id: int, office_id: int) -> Office:
    office = state.office(office_id)
    if office is None or office.company_id != company_id or office.status != "open":
        raise GeoRuleError(f"no open office {office_id}")
    return office


def lease_office(
    state: GameState,
    action: LeaseOffice,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    """Immediate, energy 10: a lease of 25, 50, 100 or 250 seats in a city, its fit-out paid
    at once (19.2). The rent posts each month in phase 6."""
    company = acting_company(state, action.actor_id)
    if not data.has_city(action.city):
        raise UnknownCityError(f"unknown city {action.city!r}")
    if action.seats not in balance.office.seat_sizes:
        sizes = ", ".join(str(s) for s in balance.office.seat_sizes)
        raise GeoRuleError(f"an office has {sizes} seats")
    city = data.city(action.city)
    rent = gf.lease_rent_cents(action.seats, city.rent_index, balance)
    fit_out = gf.fit_out_cents(rent, balance)
    if account_balance(balances, company, CASH) < fit_out:
        raise InsufficientCashError(f"the fit-out needs {fit_out} cents in cash")
    state = spend_energy(
        state, action.actor_id, "lease_office", balance, cost=balance.office.lease_energy
    )
    office_id, ids = state.next_ids.take("office")
    office = Office(office_id, company, action.city, action.seats, state.turn)
    state = with_office(replace(state, next_ids=ids), office)
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=company,
        memo=f"Office fit-out: {city.label}",
        debit=RENT,
        credit=CASH,
        amount=fit_out,
    )
    log = inbox_item(
        state.turn,
        company,
        "office_leased",
        city=city.label,
        seats=action.seats,
        rent_cents=rent,
        fit_out_cents=fit_out,
    )
    return Outcome(state, (entry,), (log,))


def close_office(
    state: GameState, action: CloseOffice, balance: Balance, data: GameData
) -> Outcome:
    """Immediate, energy 10: 3 months' rent as a penalty. Its units move to flexible space
    in the HQ city, or work remotely from that city when it is not the HQ city (19.2)."""
    company = acting_company(state, action.actor_id)
    office = open_office(state, company, action.office_id)
    state = spend_energy(
        state, action.actor_id, "close_office", balance, cost=balance.office.close_energy
    )
    state = settle_home_cities(state, company, balance, data)  # they live where they worked
    at_hq = office.city == hq_city(state.company(company), balance)
    for unit in state.active_units(company):
        if unit.office_id == office.id:
            state = with_unit(
                state, replace(unit, office_id=None, policy=unit.policy if at_hq else "remote")
            )
    state = with_office(state, replace(office, status="closed", closed_turn=state.turn))
    penalty = gf.close_penalty_cents(office_rent_cents(office, balance, data), balance)
    city = data.city(office.city)
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=company,
        memo=f"Office lease ended early: {city.label}",
        debit=RENT,
        credit=CASH,
        amount=penalty,
    )
    log = inbox_item(state.turn, company, "office_closed", city=city.label, penalty_cents=penalty)
    return Outcome(state, (entry,), (log,))


def set_unit_office(
    state: GameState, action: SetUnitOffice, balance: Balance, data: GameData
) -> Outcome:
    """Immediate, energy 2: the unit works from an office (and so under an office policy),
    or from its parent's again (19.2). Its members move with it (M9 brief: moving a unit to
    another office is the one way staff change city)."""
    company = acting_company(state, action.actor_id)
    unit = active_unit(state, company, action.unit_id)
    if action.office_id is not None:
        open_office(state, company, action.office_id)
    if unit.office_id == action.office_id:
        raise GeoRuleError(f"{unit.name} already works there")
    state = spend_energy(
        state, action.actor_id, "set_unit_office", balance, cost=balance.office.assign_energy
    )
    policy = "office" if action.office_id is not None else unit.policy
    state = with_unit(state, replace(unit, office_id=action.office_id, policy=policy))
    return Outcome(settle_home_cities(state, company, balance, data))


@dataclass(frozen=True, slots=True)
class LaunchInRegion:
    actor_id: int
    product_id: int
    region: str
    kind: Literal["launch_in_region"] = "launch_in_region"


@dataclass(frozen=True, slots=True)
class SetRegionalPrice:
    actor_id: int
    product_id: int
    region: str
    segment: str
    price_cents: int
    kind: Literal["set_regional_price"] = "set_regional_price"


type GeoAction = LeaseOffice | CloseOffice | SetUnitOffice | LaunchInRegion | SetRegionalPrice


def default_regional_price(
    state: GameState, category: str, segment: str, region: str, balance: Balance, data: GameData
) -> int:
    """`p_ref x price index`, the default price in a region (19.5)."""
    reference = data.category(category).market(segment).reference_price_cents
    return gf.regional_price_cents(reference, region, home_region(state, balance, data), data)


def launch_problem(
    state: GameState, product_id: int, region: str, balance: Balance, data: GameData
) -> str | None:
    """Why the product cannot launch in `region` now, or None (19.5)."""
    product = state.product(product_id)
    if product is None:
        return "no such product"
    if region not in data.region_keys:
        return f"unknown region {region!r}"
    if region == home_region(state, balance, data):
        return "it already sells in its home region"
    if product.status != "live":
        return "it must be live at home first"
    if state.product_region(product.id, region) is not None:
        return "it has already launched there"
    if not any(s.price_cents is not None for s in state.segments_of(product.id)):
        return "it has no priced segment at home"
    return None


def launch_in_region(
    state: GameState,
    action: LaunchInRegion,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    """Immediate, energy 4: localization costs `$40,000 x sigma / 6` once and takes 3 months;
    the product then sells in the region at `p_ref x price index` unless the player sets
    other prices (19.5)."""
    company = acting_company(state, action.actor_id)
    product = state.product(action.product_id)
    if product is None or product.company_id != company:
        raise GeoRuleError(f"no product {action.product_id}")
    if problem := launch_problem(state, product.id, action.region, balance, data):
        raise GeoRuleError(f"{product.name} cannot launch there: {problem}")
    cost = gf.localization_cents(data.category(product.category).scope, balance)
    if account_balance(balances, company, CASH) < cost:
        raise InsufficientCashError(f"localization needs {cost} cents in cash")
    state = spend_energy(
        state, action.actor_id, "launch_in_region", balance, cost=balance.markets.launch_energy
    )
    live = state.turn + balance.markets.localize_months
    state = with_product_region(state, ProductRegion(product.id, action.region, state.turn, live))
    state = add_regional_segments(state, product.id, action.region, balance, data)
    label = data.region(action.region).label
    entry = LedgerEntry(
        turn=state.turn,
        company_id=company,
        memo=f"Localization: {product.name} for {label}",
        lines=(LedgerLine(RESEARCH, cost, product.division_id), LedgerLine(CASH, -cost)),
    )
    log = inbox_item(
        state.turn,
        company,
        "region_launched",
        link_kind="product",
        link_id=product.id,
        product=product.name,
        region=label,
        cost_cents=cost,
        live=format_turn(live),
    )
    return Outcome(state, (entry,), (log,))


def add_regional_segments(
    state: GameState, product_id: int, region: str, balance: Balance, data: GameData
) -> GameState:
    """Every home segment of the product in `region`, at the default price (19.5)."""
    product = state.product(product_id)
    assert product is not None
    for seg in state.segments_of(product_id):
        if any(s.segment == seg.segment for s in state.regional_segments_of(product_id, region)):
            continue
        price = default_regional_price(state, product.category, seg.segment, region, balance, data)
        state = with_regional_segment(
            state,
            RegionalSegment(product_id, region, seg.segment, price, added_turn=state.turn),
        )
    return state


def set_regional_price(
    state: GameState, action: SetRegionalPrice, balance: Balance, data: GameData
) -> Outcome:
    """As set_price, for one segment in one region (19.5); energy as set_price."""
    company = acting_company(state, action.actor_id)
    product = state.product(action.product_id)
    if product is None or product.company_id != company:
        raise GeoRuleError(f"no product {action.product_id}")
    if state.product_region(product.id, action.region) is None:
        raise GeoRuleError(f"{product.name} has not launched in that region")
    seg = next(
        (
            s
            for s in state.regional_segments_of(product.id, action.region)
            if s.segment == action.segment
        ),
        None,
    )
    if seg is None:
        raise GeoRuleError(f"{product.name} does not sell to segment {action.segment!r} there")
    price = action.price_cents
    if isinstance(price, bool) or not isinstance(price, int) or price <= 0:
        raise GeoRuleError("a price must be a positive amount in cents")
    if seg.price_cents == price:
        raise GeoRuleError("that is already the price")
    state = spend_energy(state, action.actor_id, "set_price", balance)
    return Outcome(with_regional_segment(state, replace(seg, price_cents=price)))
