"""M8r finding 3 (Codex review 1, P2): a poached executive leaves their old company's seat.
Departure cleanup checks the seat's (unit's, plan's) own company, not "on anyone's staff":
phase 1 moves the poached person onto the rival's staff before cleanup runs."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.unit.test_hiring_phases import Game
from tests.unit.test_scaleup import FOUNDER, act, game, run, skilled
from tst.loader import LoadedData
from tst.sim.actions import AppointExecutive, CreateUnit, MovePerson, SetLeader
from tst.sim.org import executives as ex
from tst.sim.rivals.decisions import approach
from tst.sim.state import with_approach, with_person

CTO, NEXT = 2, 3


def test_a_poached_cto_leaves_the_seat_vacant(loaded: LoadedData) -> None:
    state = skilled(game(loaded, staff=2), CTO, 14.0)
    state = run(loaded, state, AppointExecutive(FOUNDER, "cto", CTO))
    state = run(loaded, state, CreateUnit(FOUNDER, "team", "Platform"))
    team = max(u.id for u in state.units)
    state = run(loaded, state, MovePerson(FOUNDER, CTO, team), SetLeader(FOUNDER, team, CTO))
    assert ex.effect_of(state, 1, "cto", loaded.balance) == pytest.approx(0.5)

    rival = next(c for c in state.companies if c.name == "Salesforce")
    state = approach(state, rival, CTO, loaded.balance, loaded.game_data)
    person = state.person(CTO)  # an unhappy, disloyal person takes a huge offer
    disloyal = person.personality.updated({"loyalty": 1.0})
    state = with_person(state, replace(person, personality=disloyal))
    state = with_approach(state, replace(state.approaches[0], offer_cents=40_000_000))
    g = Game(loaded, state, 400_000_000)
    notes: list[str] = []
    for _ in range(4):
        notes += [i.template or "" for i in g.turn().log_items]
        joined = g.state.employment_of(CTO)
        if joined is not None and joined.company_id == rival.id:
            break
    else:
        pytest.fail("the CTO never joined the rival")

    state = g.state
    assert state.seat_holder(1, "cto") is None
    assert ex.effect_of(state, 1, "cto", loaded.balance) == loaded.balance.exec_seats.vacant_effect
    assert "exec_left" in notes and "unit_leader_left" in notes
    assert next(u for u in state.units if u.id == team).leader_id is None
    state = act(
        loaded, skilled(state, NEXT, 12.0), AppointExecutive(FOUNDER, "cto", NEXT)
    ).new_state
    assert state.seat_holder(1, "cto") == NEXT


def test_a_holder_employed_elsewhere_counts_as_vacant(loaded: LoadedData) -> None:
    """effect_of, before cleanup has run: a holder whose employment is at another company."""
    state = skilled(game(loaded, staff=2), CTO, 14.0)
    state = run(loaded, state, AppointExecutive(FOUNDER, "cto", CTO))
    employment = state.employment_of(CTO)
    assert employment is not None
    from tst.sim.state import with_employment

    elsewhere = replace(employment, company_id=next(c.id for c in state.companies if c.id != 1))
    state = with_employment(state, elsewhere)
    assert ex.effect_of(state, 1, "cto", loaded.balance) == loaded.balance.exec_seats.vacant_effect
