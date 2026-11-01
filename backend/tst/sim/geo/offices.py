"""Who sits in which office, what each head costs, and crowding (docs/formulas.md 19.2)."""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.geo import formulas as gf
from tst.sim.geo.cities import hq_city, unit_office_id
from tst.sim.ledger import AccountCode
from tst.sim.money import Cents
from tst.sim.org.rules import is_remote
from tst.sim.people.models import Employment
from tst.sim.state import GameState


def office_of(state: GameState, employment: Employment) -> int | None:
    """The open office someone works in; None for flexible HQ space or remote work."""
    if is_remote(state, employment):
        return None
    office_id = unit_office_id(state, employment.unit_id)
    office = state.office(office_id) if office_id is not None else None
    return office.id if office is not None and office.status == "open" else None


def office_members(state: GameState, company_id: int) -> dict[int, list[int]]:
    """Person ids working in each open office of the company, by office id."""
    members: dict[int, list[int]] = {o.id: [] for o in state.company_offices(company_id)}
    if not members:
        return members
    for employment in state.staff(company_id):
        office_id = office_of(state, employment)
        if office_id in members:
            members[office_id].append(employment.person_id)
    return members


def crowded_people(state: GameState, company_id: int) -> set[int]:
    """Everyone in an office whose members exceed its seats (19.2)."""
    out: set[int] = set()
    for office_id, people in office_members(state, company_id).items():
        office = state.office(office_id)
        if office is not None and len(people) > office.seats:
            out.update(people)
    return out


def flexible_seat_cents(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> Cents:
    """Flexible HQ space per head: `$600 x the HQ city's rent index` (19.2). Without
    cities.yaml (test data), v1's $600."""
    if not data.cities:
        return balance.payroll.office_cost_per_head_cents
    city = data.city(hq_city(state.company(company_id), balance))
    return gf.flexible_seat_cents(city.rent_index, balance)


def employee_office_cents(
    state: GameState, employment: Employment, balance: Balance, data: GameData
) -> Cents:
    """One employee's office cost a month: none remote or in a leased office (its rent covers
    the seat), else flexible space at the HQ city's rate (8, 19.2)."""
    if is_remote(state, employment) or office_of(state, employment) is not None:
        return 0
    return flexible_seat_cents(state, employment.company_id, balance, data)


def rent_lines(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> list[tuple[str, AccountCode, Cents, int | None]]:
    """Each open lease's rent, full or not, to 6100_rent, corporate (19.2)."""
    from tst.sim.ledger import RENT

    return [
        (
            f"Rent: {data.city(o.city).label}",
            RENT,
            gf.lease_rent_cents(o.seats, data.city(o.city).rent_index, balance),
            None,
        )
        for o in state.company_offices(company_id)
    ]
