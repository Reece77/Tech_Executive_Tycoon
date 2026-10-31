"""Scale-up actions (ADR-0014, docs/formulas.md 18): a product's division, a division's
shared services, and appointing or removing executives. Divisions themselves are created,
moved, led and dissolved with the organization actions (actions/org.py)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError, OrgRuleError, ProductRuleError
from tst.sim.hiring.formulas import market_mid_cents
from tst.sim.log import inbox_item
from tst.sim.org.executives import level_allowed, seats_in_play
from tst.sim.org.models import SEATS, SHARED_SERVICES, ExecSeat, OrgUnit, SharedServices
from tst.sim.state import GameState, with_employment, with_exec_seat, with_product, with_unit

EXEC_LEVEL = "exec"  # tunable-exempt: the level a seat holder takes (18.3)


@dataclass(frozen=True, slots=True)
class SetProductDivision:
    actor_id: int
    product_id: int
    division_id: int | None  # None = corporate
    kind: Literal["set_product_division"] = "set_product_division"


@dataclass(frozen=True, slots=True)
class SetSharedServices:
    actor_id: int
    unit_id: int
    services: SharedServices
    kind: Literal["set_shared_services"] = "set_shared_services"


@dataclass(frozen=True, slots=True)
class AppointExecutive:
    actor_id: int
    seat: str
    person_id: int
    # The new annual salary; None: the person's exec market rate, never below their current
    # pay (18.3; product manager, 2026-10-31).
    salary_cents: int | None = None
    kind: Literal["appoint_executive"] = "appoint_executive"


@dataclass(frozen=True, slots=True)
class RemoveExecutive:
    actor_id: int
    seat: str
    kind: Literal["remove_executive"] = "remove_executive"


type ScaleupAction = SetProductDivision | SetSharedServices | AppointExecutive | RemoveExecutive


def division_unit(state: GameState, company_id: int, unit_id: int) -> OrgUnit:
    unit = state.unit(unit_id)
    if unit is None or unit.company_id != company_id or unit.status != "active":
        raise OrgRuleError(f"no unit {unit_id}")
    if unit.kind != "division":
        raise OrgRuleError(f"{unit.name} is not a division")
    return unit


def is_president(state: GameState, person_id: int) -> bool:
    return any(
        u.kind == "division" and u.status == "active" and u.leader_id == person_id
        for u in state.units
    )


def set_product_division(state: GameState, action: SetProductDivision, balance: Balance) -> Outcome:
    """Immediate, energy 1: reporting and the cross-division factor only (18.1)."""
    company = acting_company(state, action.actor_id)
    product = state.product(action.product_id)
    if product is None or product.company_id != company or product.status == "retired":
        raise ProductRuleError(f"no product {action.product_id}")
    if action.division_id is not None:
        division_unit(state, company, action.division_id)
    if product.division_id == action.division_id:
        raise ProductRuleError(f"{product.name} already belongs there")
    state = spend_energy(state, action.actor_id, "set_product_division", balance)
    return Outcome(with_product(state, replace(product, division_id=action.division_id)))


def set_shared_services(state: GameState, action: SetSharedServices, balance: Balance) -> Outcome:
    """Immediate, energy 2: central (the default) or embedded (18.4)."""
    company = acting_company(state, action.actor_id)
    if action.services not in SHARED_SERVICES:
        raise OrgRuleError(f"unknown shared services {action.services!r}")
    unit = division_unit(state, company, action.unit_id)
    if (unit.services or "central") == action.services:
        raise OrgRuleError(f"{unit.name} already uses {action.services} shared services")
    state = spend_energy(state, action.actor_id, "set_shared_services", balance)
    return Outcome(with_unit(state, replace(unit, services=action.services)))


def _seat(state: GameState, company: int, seat: str, balance: Balance) -> None:
    if seat not in SEATS or seat not in balance.exec_seats.seats:
        raise InvalidActionError(f"unknown executive seat {seat!r}")
    if not seats_in_play(state, company, balance):
        raise OrgRuleError(f"executive seats open at stage {balance.exec_seats.stage}")


def appoint_problem(
    state: GameState, company: int, seat: str, person_id: int, balance: Balance
) -> str | None:
    """Why `person_id` cannot take `seat` now, or None (18.3)."""
    employment = state.employment_of(person_id)
    if employment is None or employment.company_id != company:
        return "they are not on staff"
    if state.person(person_id).is_founder:
        return "the founder stays CEO"
    if not level_allowed(employment.level, balance):
        return f"a seat needs someone at {balance.exec_seats.min_level} level or above"
    if state.seat_of(person_id) is not None:
        return "they already hold a seat"
    if is_president(state, person_id):
        return "a division president cannot hold a seat"
    if state.seat_holder(company, seat) is not None:
        return f"the {seat.upper()} seat is filled; remove its holder first"
    return None


def exec_salary_cents(state: GameState, person_id: int, data: GameData) -> int:
    """The default salary on appointment: the exec market rate for the person's role and
    region, never below what they are paid now (18.3; product manager, 2026-10-31)."""
    employment = state.employment_of(person_id)
    assert employment is not None
    band = data.role(employment.role).salary_band_mid_cents[EXEC_LEVEL]
    region = data.region(state.person(person_id).region)
    return max(employment.salary_cents, market_mid_cents(band, region.salary_multiplier_bp))


def appoint_executive(
    state: GameState, action: AppointExecutive, balance: Balance, data: GameData
) -> Outcome:
    """Energy 5: the appointee becomes exec level at the new salary, at once, and gains +5
    morale once, plus the raise bonus once under the 13.8 rules (18.3). Without the raise,
    rivals' offers at the exec market rate took appointees within months (M8r)."""
    company = acting_company(state, action.actor_id)
    _seat(state, company, action.seat, balance)
    if problem := appoint_problem(state, company, action.seat, action.person_id, balance):
        raise OrgRuleError(problem)
    from tst.sim.actions.org import bump_morale, raise_morale_change

    employment = state.employment_of(action.person_id)
    assert employment is not None
    salary = action.salary_cents
    if salary is None:
        salary = exec_salary_cents(state, action.person_id, data)
    if isinstance(salary, bool) or not isinstance(salary, int) or salary <= 0:
        raise InvalidActionError("a salary must be a positive amount in cents")
    if salary < employment.salary_cents:
        raise OrgRuleError("an appointment cannot set a salary below their current pay")
    state = spend_energy(state, action.actor_id, "appoint_executive", balance)
    raise_bonus = raise_morale_change(employment, salary, state.turn, balance)
    last = state.turn if raise_bonus > 0 else employment.last_raise_turn
    state = with_employment(
        state,
        replace(employment, level=EXEC_LEVEL, salary_cents=salary, last_raise_turn=last),
    )
    state = with_exec_seat(state, ExecSeat(company, action.seat, action.person_id, state.turn))
    state = bump_morale(state, action.person_id, balance.exec_seats.appoint_morale + raise_bonus)
    person = state.person(action.person_id)
    label = balance.exec_seats.seats[action.seat].label
    log = inbox_item(
        state.turn,
        company,
        "exec_appointed",
        link_kind="person",
        link_id=person.id,
        name=f"{person.first_name} {person.last_name}",
        seat=label,
    )
    return Outcome(state, log=(log,))


def remove_executive(state: GameState, action: RemoveExecutive, balance: Balance) -> Outcome:
    """Energy 5: -10 morale once; their level stays exec (18.3)."""
    company = acting_company(state, action.actor_id)
    _seat(state, company, action.seat, balance)
    holder = state.seat_holder(company, action.seat)
    if holder is None:
        raise OrgRuleError(f"the {action.seat.upper()} seat is already vacant")
    from tst.sim.actions.org import bump_morale

    state = spend_energy(state, action.actor_id, "remove_executive", balance)
    state = with_exec_seat(state, ExecSeat(company, action.seat, None, state.turn))
    state = bump_morale(state, holder, balance.exec_seats.remove_morale)
    person = state.person(holder)
    log = inbox_item(
        state.turn,
        company,
        "exec_removed",
        link_kind="person",
        link_id=person.id,
        name=f"{person.first_name} {person.last_name}",
        seat=balance.exec_seats.seats[action.seat].label,
    )
    return Outcome(state, log=(log,))
