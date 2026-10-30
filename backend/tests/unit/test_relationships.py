"""Relationships (docs/formulas.md 16.7, M6 sub-task 2): pairs of unit-mates and manager
links only, start from temperament, tag pushes and drift, values in [-100, 100], and W_rel
in morale. A credit-taker's unit-mate settles near the 16.11 value (-24)."""

from __future__ import annotations

import dataclasses
from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game, make_person, with_employee
from tests.unit.test_hiring_phases import Game
from tests.unit.test_org_rules import team
from tst.loader import LoadedData
from tst.sim.org.morale import morale_terms
from tst.sim.org.relationships import relationships_month, tracked_pairs
from tst.sim.org.rules import org_view
from tst.sim.people.models import Person
from tst.sim.people.relationships import (
    pair_key,
    relationship_step,
)
from tst.sim.state import GameState, with_employment, with_unit

FOUNDER = 1


def _person(loaded: LoadedData, pid: int, temperament: float, tags: tuple[str, ...] = ()) -> Person:
    person = make_person(loaded, pid)
    return replace(
        person,
        tags=tags,
        personality=person.personality.updated({"temperament": temperament}),
    )


def _company(loaded: LoadedData, people: list[Person]) -> GameState:
    state = fresh_game(loaded)
    for person in people:
        state = with_employee(loaded, state, person, 9_000_000)
    return state


@settings(max_examples=300, deadline=None)
@given(
    value=st.floats(-100, 100),
    start=st.floats(-20, 15),
    push=st.floats(-60, 60),
    months=st.integers(1, 40),
)
def test_relationships_stay_in_range(
    loaded: LoadedData, value: float, start: float, push: float, months: int
) -> None:
    cfg = loaded.balance.relationships
    for _ in range(months):
        value = relationship_step(value, start, push, cfg)
        assert -100 <= value <= 100


@settings(max_examples=25, deadline=None)
@given(
    units=st.lists(st.sampled_from([None, 1, 2]), min_size=2, max_size=6), turns=st.integers(1, 3)
)
def test_pairs_exist_only_for_unit_mates_and_manager_links(
    loaded: LoadedData, units: list[int | None], turns: int
) -> None:
    people = [_person(loaded, 2 + i, 5 + 2 * i) for i in range(len(units))]
    state = _company(loaded, people)
    state = with_unit(state, team(1, leader=people[0].id))
    state = with_unit(state, team(2, leader=None, parent=1))
    for person, unit in zip(people, units, strict=True):
        employment = next(e for e in state.staff(1) if e.person_id == person.id)
        state = with_employment(state, replace(employment, unit_id=unit))
    for _ in range(turns):
        state = relationships_month(state, loaded.balance)
        allowed, _ = tracked_pairs(state, 1)
        assert {r.key for r in state.relationships} == allowed
        view = org_view(state, 1)
        for r in state.relationships:
            same_unit = view.unit_of[r.a] == view.unit_of[r.b]
            managed = view.manager_of.get(r.a) == r.b or view.manager_of.get(r.b) == r.a
            assert same_unit or managed
            assert -100 <= r.value <= 100


def test_a_credit_takers_unit_mate_settles_near_minus_24(loaded: LoadedData) -> None:
    """16.11: temperaments 14 and 6 start at 3; the credit-taker pushes -3 a month and the
    pair settles at -24, where it pulls the mate's W_rel down. Resignations are off: the
    example is about drift, and at M7a's base rate one of the two could leave within 60 months."""
    balance = loaded.balance.model_copy(
        update={"resign": loaded.balance.resign.model_copy(update={"base_bp": 0})}
    )
    loaded = dataclasses.replace(loaded, balance=balance)
    taker = _person(loaded, 2, 14, ("credit_taker",))
    mate = _person(loaded, 3, 6)
    state = _company(loaded, [taker, mate])
    game = Game(loaded, state, 400_000_000)
    key = pair_key(taker.id, mate.id)
    seen = []
    for _ in range(60):
        game.turn()
        seen.append(game.state.relationship_map()[key].value)
    assert seen[0] == 3  # the pair starts in its first phase 8
    assert seen[1] == pytest.approx(0.3) and seen[2] == pytest.approx(-2.13)
    assert seen[-1] == pytest.approx(-24, abs=0.1)
    # The founder is a unit-mate too (the root) and is pushed the same way.
    founder_pair = game.state.relationship_map()[pair_key(FOUNDER, taker.id)]
    assert founder_pair.value < founder_pair.start
    view = org_view(game.state, 1)
    employment = next(e for e in game.state.staff(1) if e.person_id == mate.id)
    terms = morale_terms(game.state, view, employment, loaded.balance, loaded.game_data, 0, 0)
    mates = [game.state.relationship_map()[pair_key(mate.id, m)].value for m in (FOUNDER, taker.id)]
    assert terms.relationships == pytest.approx(max(-5.0, min(5.0, 0.1 * sum(mates) / len(mates))))
    assert all(tag != "credit_taker" for tag, _, _ in terms.team)  # 13.6 now via relationships


def test_tag_pushes(loaded: LoadedData) -> None:
    """Culture carriers lift every unit-mate; a politician pushes only ambitious ones."""
    carrier = _person(loaded, 2, 10, ("culture_carrier",))
    carrier = replace(carrier, personality=carrier.personality.updated({"ambition": 5}))
    politician = _person(loaded, 3, 10, ("politician",))
    calm = replace(
        _person(loaded, 4, 10),
        personality=_person(loaded, 4, 10).personality.updated({"ambition": 5}),
    )
    keen = replace(
        _person(loaded, 5, 10),
        personality=_person(loaded, 5, 10).personality.updated({"ambition": 16}),
    )
    state = _company(loaded, [carrier, politician, calm, keen])
    state = relationships_month(state, loaded.balance)  # pairs start
    start = state.relationship_map()
    state = relationships_month(state, loaded.balance)
    after = state.relationship_map()

    def moved(x: int, y: int) -> float:
        k = pair_key(x, y)
        return after[k].value - start[k].value

    assert moved(carrier.id, calm.id) == pytest.approx(2 * 0.9)  # +2, then drift from start
    assert moved(politician.id, calm.id) == 0  # ambition 5: not pushed
    assert moved(politician.id, keen.id) == pytest.approx(-3 * 0.9)
    assert moved(carrier.id, politician.id) == pytest.approx(2 * 0.9)


def test_pairs_end_when_people_leave_or_move(loaded: LoadedData) -> None:
    a, b = _person(loaded, 2, 10), _person(loaded, 3, 10)
    state = _company(loaded, [a, b])
    state = relationships_month(state, loaded.balance)
    assert pair_key(a.id, b.id) in state.relationship_map()
    leaving = next(e for e in state.staff(1) if e.person_id == b.id)
    state = with_employment(state, replace(leaving, status="ended", end_turn=state.turn))
    state = relationships_month(state, loaded.balance)
    assert all(b.id not in r.key for r in state.relationships)
