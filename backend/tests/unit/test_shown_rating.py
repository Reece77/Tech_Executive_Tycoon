"""The shown rating (M7b, formulas.md 17.2): the mean midpoint of displayed ranges only."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.helpers import make_person
from tst.loader import LoadedData
from tst.sim.people.reveal import new_reveal_state, revealed_range, shown_rating
from tst.sim.rng import RngFactory

PERSON = 7


def test_shown_rating_is_the_mean_displayed_midpoint(loaded: LoadedData) -> None:
    person = make_person(loaded, PERSON)
    reveal = new_reveal_state(
        observer_company_id=1,
        person=person,
        turn=0,
        rng=RngFactory(1),
        data=loaded.game_data,
        balance=loaded.balance,
    )
    skills = ("software_engineering", "ml_research")
    mids = [sum(revealed_range(person, reveal, k)) / 2 for k in skills]
    assert shown_rating(person, reveal, skills) == sum(mids) / 2
    assert shown_rating(person, reveal, ()) == 0.0


@settings(max_examples=25, deadline=None)
@given(st.floats(min_value=1.0, max_value=20.0))
def test_shown_rating_stays_on_the_scale(loaded: LoadedData, value: float) -> None:
    person = make_person(loaded, PERSON)
    person = replace(
        person, skills=person.skills.updated({k: value for k, _ in person.skills.items})
    )
    reveal = new_reveal_state(
        observer_company_id=1,
        person=person,
        turn=0,
        rng=RngFactory(2),
        data=loaded.game_data,
        balance=loaded.balance,
    )
    keys = tuple(k for k, _ in person.skills.items)[:3]
    assert 1.0 <= shown_rating(person, reveal, keys) <= 20.0
