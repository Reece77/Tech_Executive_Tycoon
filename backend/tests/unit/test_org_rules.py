"""Org rules (formulas.md 13): reporting lines, span, morale terms, growth, office cost."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, make_person, with_employee
from tst.loader import LoadedData
from tst.sim.hiring.phases import monthly_costs
from tst.sim.ledger import RENT
from tst.sim.org.models import OrgUnit
from tst.sim.org.morale import morale_terms
from tst.sim.org.rules import effective_policy, manager_terms, org_view
from tst.sim.people.formulas import growth_delta
from tst.sim.state import GameState, with_company, with_employment, with_person, with_unit

FOUNDER = 1


def staffed(loaded: LoadedData, count: int, first: int = 2) -> GameState:
    """A fresh game (engineer founder) with `count` mid software engineers in the root."""
    state = fresh_game(loaded)
    for pid in range(first, first + count):
        state = with_employee(loaded, state, make_person(loaded, pid), 9_000_000)
    return state


def set_skills(state: GameState, person_id: int, **skills: float) -> GameState:
    person = state.person(person_id)
    return with_person(state, replace(person, skills=person.skills.updated(skills)))


def set_tags(state: GameState, person_id: int, *tags: str) -> GameState:
    return with_person(state, replace(state.person(person_id), tags=tags))


def put(state: GameState, person_id: int, unit_id: int | None) -> GameState:
    employment = state.employment_of(person_id)
    assert employment is not None
    return with_employment(state, replace(employment, unit_id=unit_id))


def team(unit_id: int, leader: int | None, parent: int | None = None) -> OrgUnit:
    return OrgUnit(unit_id, 1, "team", f"Team {unit_id}", parent, leader, None, created_turn=0)


def terms(loaded: LoadedData, state: GameState, person_id: int) -> float:
    view = org_view(state, 1)
    employment = state.employment_of(person_id)
    assert employment is not None
    cash = 10**9
    return morale_terms(
        state, view, employment, loaded.balance, loaded.game_data, cash, cash
    ).manager


def test_founder_managing_twelve_directly(loaded: LoadedData) -> None:
    state = staffed(loaded, 12)
    view = org_view(state, 1)
    assert view.manager_of[FOUNDER] is None
    assert all(view.manager_of[p] == FOUNDER for p in range(2, 14))
    assert view.reports[FOUNDER] == tuple(range(2, 14))
    mt = manager_terms(state, view, 2, loaded.balance)
    assert (mt.span_limit, mt.reports) == (7, 12)
    assert mt.morale == pytest.approx(-3.68, abs=5e-3)
    assert mt.growth == pytest.approx(0.90, abs=5e-3)
    assert terms(loaded, state, 2) == pytest.approx(-3.68, abs=5e-3)
    founder = manager_terms(state, view, FOUNDER, loaded.balance)
    assert (founder.manager_id, founder.morale, founder.growth) == (None, 0.0, 1.0)


def test_two_leads_remove_the_founder_penalty(loaded: LoadedData) -> None:
    state = staffed(loaded, 12)
    for lead in (2, 3):
        state = set_skills(state, lead, leadership=14, communication=12, mentoring=10)
    state = with_unit(state, team(1, leader=2))
    state = with_unit(state, team(2, leader=3))
    for pid in range(2, 14):
        state = put(state, pid, 1 if pid % 2 == 0 else 2)
    view = org_view(state, 1)
    assert view.reports[FOUNDER] == (2, 3)
    assert view.manager_of[4] == 2 and view.manager_of[5] == 3
    assert terms(loaded, state, 2) == pytest.approx(-0.60)  # the leads report to the founder
    assert terms(loaded, state, 4) == pytest.approx(2.0)  # 5 reports, Q = 12.5
    mt = manager_terms(state, view, 4, loaded.balance)
    assert mt.growth == pytest.approx(1.25)


def test_leaderless_units_and_leaders_look_one_level_up(loaded: LoadedData) -> None:
    state = staffed(loaded, 5)
    dept = OrgUnit(1, 1, "department", "Eng", None, 2, None, created_turn=0)
    state = with_unit(state, dept)
    state = with_unit(state, team(2, leader=3, parent=1))
    state = with_unit(state, team(3, leader=None, parent=1))
    state = put(put(put(put(state, 2, 1), 3, 2), 4, 2), 5, 3)
    view = org_view(state, 1)
    assert view.manager_of == {FOUNDER: None, 2: FOUNDER, 3: 2, 4: 3, 5: 2, 6: FOUNDER}
    # Without the department leader, the team lead reports to the founder.
    view = org_view(with_unit(state, replace(dept, leader_id=None)), 1)
    assert view.manager_of[3] == FOUNDER and view.manager_of[5] == FOUNDER


def test_teammate_tags_affect_only_the_unit(loaded: LoadedData) -> None:
    state = staffed(loaded, 4)
    state = with_unit(state, team(1, leader=None))
    state = put(put(state, 2, 1), 3, 1)
    state = set_tags(state, 3, "toxic_high_performer")
    view = org_view(state, 1)
    employment = state.employment_of(2)
    assert employment is not None
    mt = morale_terms(state, view, employment, loaded.balance, loaded.game_data, 1, 1)
    assert dict((t, v) for t, _, v in mt.team)["toxic_high_performer"] == -3
    holder = state.employment_of(3)
    assert holder is not None
    own = morale_terms(state, view, holder, loaded.balance, loaded.game_data, 1, 1)
    assert own.team_total == 0  # not the holder
    outsider = state.employment_of(4)
    assert outsider is not None
    other = morale_terms(state, view, outsider, loaded.balance, loaded.game_data, 1, 1)
    assert other.team_total == 0


def test_mentor_teammate_raises_growth(loaded: LoadedData) -> None:
    state = staffed(loaded, 3)
    state = set_skills(state, 2, leadership=14, communication=12, mentoring=10)
    state = with_unit(state, team(1, leader=2))
    state = put(put(put(state, 2, 1), 3, 1), 4, 1)
    state = set_tags(state, 4, "mentor")
    view = org_view(state, 1)
    assert manager_terms(state, view, 3, loaded.balance).growth == pytest.approx(1.40)
    assert manager_terms(state, view, 4, loaded.balance).growth == pytest.approx(1.25)


def test_policy_inherits_and_remote_staff_cost_no_office(loaded: LoadedData) -> None:
    state = staffed(loaded, 3)
    state = with_unit(state, OrgUnit(1, 1, "department", "D", None, None, "remote", 0))
    state = with_unit(state, team(2, leader=None, parent=1))
    state = put(put(state, 2, 1), 3, 2)
    assert effective_policy(state, 1, 2) == "remote"
    assert effective_policy(state, 1, None) == "office"
    office = dict((acc, amt) for _, acc, amt in monthly_costs(state, 1, loaded.balance))[RENT]
    per_head = loaded.balance.payroll.office_cost_per_head_cents
    assert office == 2 * per_head  # the founder and person 4; persons 2 and 3 are remote
    state = with_company(state, replace(state.player, work_policy="remote"))
    office = dict((acc, amt) for _, acc, amt in monthly_costs(state, 1, loaded.balance))[RENT]
    assert office == 0


def test_remote_morale_term(loaded: LoadedData) -> None:
    state = staffed(loaded, 1)
    person = state.person(2)
    state = with_person(
        state, replace(person, personality=person.personality.updated({"sociability": 16}))
    )
    state = with_company(state, replace(state.player, work_policy="remote"))
    employment = state.employment_of(2)
    assert employment is not None
    mt = morale_terms(state, org_view(state, 1), employment, loaded.balance, loaded.game_data, 1, 1)
    assert mt.remote == -3


def test_growth_uses_the_multiplier(loaded: LoadedData) -> None:
    growth = loaded.balance.growth
    base = growth_delta(in_role=True, age=24, ca=106, pa=160, professionalism=14, growth=growth)
    boosted = growth_delta(
        in_role=True, age=24, ca=106, pa=160, professionalism=14, growth=growth, mentoring=1.25
    )
    assert boosted == pytest.approx(base * 1.25)
