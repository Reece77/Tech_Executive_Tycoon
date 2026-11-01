"""Where people live and work (docs/formulas.md 19.1-19.3, M9).

A person's home city is `person.city`, or the first city of their region for people made
before M9. They work in their unit's office city (inherited from the parent unit, up to
flexible space in the HQ city) under an office policy, or from their home city when remote.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.org.rules import is_remote
from tst.sim.people.models import Employment, Person
from tst.sim.state import CompanyState, GameState, with_person


def home_city(person: Person, data: GameData) -> str:
    return person.city if person.city is not None else data.region_city(person.region)


def hq_city(company: CompanyState, balance: Balance) -> str:
    return company.hq_city or balance.geo.default_hq_city


def home_region(state: GameState, balance: Balance, data: GameData) -> str:
    """The player's HQ city's region: its markets are v1's (19.5)."""
    return data.city(hq_city(state.player, balance)).region


def unit_office_id(state: GameState, unit_id: int | None) -> int | None:
    """A unit's office: its own, else its parent's, up to the root (None = flexible HQ)."""
    seen = 0
    while unit_id is not None and seen < len(state.units) + 1:
        unit = state.unit(unit_id)
        if unit is None:
            return None
        if unit.office_id is not None:
            return unit.office_id
        unit_id = unit.parent_id
        seen += 1
    return None


def office_city(state: GameState, company_id: int, unit_id: int | None, balance: Balance) -> str:
    """The city an office-policy unit works in: its office's, else the HQ city (19.2)."""
    office_id = unit_office_id(state, unit_id)
    office = state.office(office_id) if office_id is not None else None
    if office is not None and office.status == "open":
        return office.city
    return hq_city(state.company(company_id), balance)


def work_city(state: GameState, employment: Employment, balance: Balance, data: GameData) -> str:
    """Where someone works (19.1): the office city, or their home city when remote. Rivals
    have no offices: their people work from home (M9 brief, out of scope)."""
    person = state.person(employment.person_id)
    company = state.company(employment.company_id)
    if not company.is_player or is_remote(state, employment):
        return home_city(person, data)
    return office_city(state, employment.company_id, employment.unit_id, balance)


def person_work_city(state: GameState, person: Person, balance: Balance, data: GameData) -> str:
    """Work city of a person on staff; the founder works in the HQ city; else home."""
    employment = state.employment_of(person.id)
    if employment is None:
        return home_city(person, data)
    if person.is_founder:
        return hq_city(state.company(employment.company_id), balance)
    return work_city(state, employment, balance, data)


def work_region(state: GameState, person: Person, balance: Balance, data: GameData) -> str:
    return data.city(person_work_city(state, person, balance, data)).region


def work_multiplier_bp(
    state: GameState, employment: Employment, balance: Balance, data: GameData
) -> int:
    """The salary multiplier of the city someone works in (19.1). Without cities.yaml
    (test data), their region's, as in v1."""
    if not data.cities:
        return data.region(state.person(employment.person_id).region).salary_multiplier_bp
    return data.city(work_city(state, employment, balance, data)).salary_multiplier_bp


def settle_home_cities(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> GameState:
    """Everyone working at an office lives in its city: a hire who relocated, or a unit moved
    to another office (19.2-19.3). Runs after player actions and phase 1's hires, so going
    remote or closing an office leaves people where they last worked. Not for rivals."""
    company = state.company(company_id)
    if not company.is_player or not data.cities:
        return state
    for employment in state.staff(company_id):
        if is_remote(state, employment):
            continue
        person = state.person(employment.person_id)
        city = (
            hq_city(company, balance)
            if person.is_founder
            else office_city(state, company_id, employment.unit_id, balance)
        )
        if person.city != city:
            state = with_person(state, replace(person, city=city))
    return state
