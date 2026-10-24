"""Reporting-line invariants (formulas.md 13.1) over random org charts.

Every non-founder has exactly one manager, nobody manages themselves, following managers
always reaches the founder (no cycles), and the founder has none.
"""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game, make_person, with_employee
from tst.loader import load_all
from tst.sim.org.models import OrgUnit
from tst.sim.org.rules import OrgView, org_view
from tst.sim.state import GameState, with_employment, with_unit

LOADED = load_all(DATA_DIR)
BASE = fresh_game(LOADED)
FOUNDER = 1


@st.composite
def org_charts(draw: st.DrawFn) -> GameState:
    staff = draw(st.integers(min_value=0, max_value=14))
    departments = draw(st.integers(min_value=0, max_value=3))
    teams = draw(st.integers(min_value=0, max_value=5))
    state = BASE
    for pid in range(2, 2 + staff):
        state = with_employee(LOADED, state, make_person(LOADED, pid), 9_000_000)
    units: list[OrgUnit] = []
    for i in range(departments):
        units.append(OrgUnit(i + 1, 1, "department", f"D{i}", None, None, None, 0))
    dept_ids = [u.id for u in units]
    for i in range(teams):
        parent = draw(st.sampled_from([None, *dept_ids]))
        units.append(OrgUnit(len(units) + 1, 1, "team", f"T{i}", parent, None, None, 0))
    unit_ids = [u.id for u in units]
    members: dict[int, list[int]] = {u: [] for u in unit_ids}
    for pid in range(2, 2 + staff):
        unit = draw(st.sampled_from([None, *unit_ids]))
        employment = state.employment_of(pid)
        assert employment is not None
        state = with_employment(state, replace(employment, unit_id=unit))
        if unit is not None:
            members[unit].append(pid)
    leading: set[int] = set()
    for unit in units:
        free = [p for p in members[unit.id] if p not in leading]
        leader = draw(st.sampled_from([None, *free])) if free else None
        if leader is not None:
            leading.add(leader)
        state = with_unit(state, replace(unit, leader_id=leader))
    return state


def _chain_reaches_founder(view: OrgView, person: int) -> bool:
    seen = {person}
    current = view.manager_of[person]
    while current is not None:
        if current in seen:
            return False
        seen.add(current)
        current = view.manager_of[current]
    return FOUNDER in seen


@settings(max_examples=150, deadline=None)
@given(org_charts())
def test_reporting_lines(state: GameState) -> None:
    view = org_view(state, 1)
    staff = {e.person_id for e in state.staff(1)}
    assert set(view.manager_of) == staff
    assert view.manager_of[FOUNDER] is None
    for person in staff - {FOUNDER}:
        manager = view.manager_of[person]
        assert manager is not None and manager != person and manager in staff
        assert _chain_reaches_founder(view, person)
    # Each person is somebody's direct report exactly once.
    reported = [p for reports in view.reports.values() for p in reports]
    assert sorted(reported) == sorted(staff - {FOUNDER})
    # Leaders are members of the unit they lead, and lead one unit at most.
    leaders = [u.leader_id for u in state.units if u.leader_id is not None]
    assert len(leaders) == len(set(leaders))
    for unit in state.units:
        if unit.leader_id is not None:
            assert view.unit_of[unit.leader_id] == unit.id
    assert view.unit_of[FOUNDER] is None
