"""M10r finding 3 (Codex review 2, P2): closing an office finds its effective occupants first,
child units that inherit it included (19.2). Non-HQ occupants work remotely from that city;
a child unit with its own office keeps it."""

from __future__ import annotations

from tests.helpers import fresh_game, make_person, with_employee
from tests.unit.test_geo import FOUNDER, _run
from tst.loader import LoadedData
from tst.sim.actions import CreateUnit, MovePerson, SetPolicy
from tst.sim.actions.geo import CloseOffice, LeaseOffice, SetUnitOffice
from tst.sim.geo.cities import work_city
from tst.sim.org.rules import is_remote
from tst.sim.state import GameState


def _engineering_in_berlin(loaded: LoadedData) -> GameState:
    """Engineering (department) works from Berlin; its Core team inherits that office and has
    an explicit office policy; staff 2-3 are in Core, staff 4 in the department (ten staff
    unlock departments)."""
    state = fresh_game(loaded)
    for pid in range(2, 12):
        state = with_employee(loaded, state, make_person(loaded, pid), 9_000_000, morale=60)
    state = _run(loaded, state, CreateUnit(FOUNDER, "department", "Engineering"))
    dept = state.active_units(1)[0]
    state = _run(loaded, state, CreateUnit(FOUNDER, "team", "Core", dept.id))
    core = next(u for u in state.active_units(1) if u.name == "Core")
    state = _run(
        loaded,
        state,
        MovePerson(FOUNDER, 2, core.id),
        MovePerson(FOUNDER, 3, core.id),
        MovePerson(FOUNDER, 4, dept.id),
        SetPolicy(FOUNDER, core.id, "office"),
        LeaseOffice(FOUNDER, "berlin", 25),
    )
    office = state.company_offices(1)[0]
    return _run(loaded, state, SetUnitOffice(FOUNDER, dept.id, office.id))


def test_an_inheriting_team_stays_in_berlin_remote(loaded: LoadedData) -> None:
    b, data = loaded.balance, loaded.game_data
    state = _engineering_in_berlin(loaded)
    for pid in (2, 3, 4):
        employment = state.employment_of(pid)
        assert employment is not None and work_city(state, employment, b, data) == "berlin"
        assert state.person(pid).city == "berlin"
    office = state.company_offices(1)[0]
    after = _run(loaded, state, CloseOffice(FOUNDER, office.id))
    for pid in (2, 3, 4):
        employment = after.employment_of(pid)
        assert employment is not None
        assert is_remote(after, employment), pid
        assert work_city(after, employment, b, data) == "berlin", pid
        assert after.person(pid).city == "berlin", pid
    core = next(u for u in after.active_units(1) if u.name == "Core")
    assert (core.office_id, core.policy) == (None, "remote")


def test_a_child_with_its_own_office_keeps_it(loaded: LoadedData) -> None:
    b, data = loaded.balance, loaded.game_data
    state = _engineering_in_berlin(loaded)
    berlin = state.company_offices(1)[0]
    core = next(u for u in state.active_units(1) if u.name == "Core")
    state = _run(loaded, state, LeaseOffice(FOUNDER, "london", 25))
    london = next(o for o in state.company_offices(1) if o.city == "london")
    state = _run(loaded, state, SetUnitOffice(FOUNDER, core.id, london.id))
    after = _run(loaded, state, CloseOffice(FOUNDER, berlin.id))
    core = next(u for u in after.active_units(1) if u.name == "Core")
    assert (core.office_id, core.policy) == (london.id, "office")
    employment = after.employment_of(2)
    assert employment is not None and work_city(after, employment, b, data) == "london"
    dept_member = after.employment_of(4)
    assert dept_member is not None and work_city(after, dept_member, b, data) == "berlin"
    assert is_remote(after, dept_member)
