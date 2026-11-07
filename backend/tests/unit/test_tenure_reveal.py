"""Playtest 3 addendum 13 (M15b): knowledge of the player's own employees grows with tenure:
leadership, mentoring and communication show exactly after people.reveal_tenure_months, so
long-serving staff show one leadership-fit star value; rivals' people are not affected."""

from __future__ import annotations

from dataclasses import replace

from tests.helpers import fresh_game, make_person, with_employee
from tst.loader import LoadedData
from tst.sim.hiring.phases import employed_month
from tst.sim.people.reveal import new_reveal_state, revealed_range
from tst.sim.rng import RngFactory
from tst.sim.state import with_reveal

KEYS = ("leadership", "mentoring", "communication")


def _hired(loaded: LoadedData):  # type: ignore[no-untyped-def]
    state = fresh_game(loaded)
    person = make_person(loaded, 2)
    state = with_employee(loaded, state, person, 9_000_000)
    reveal = new_reveal_state(
        observer_company_id=1,
        person=person,
        turn=0,
        rng=RngFactory(1),
        data=loaded.game_data,
        balance=loaded.balance,
        knows_exactly=False,
    )
    return with_reveal(state, reveal), person


def test_long_serving_staff_show_leadership_exactly(loaded: LoadedData) -> None:
    months = loaded.balance.people.reveal_tenure_months
    state, person = _hired(loaded)
    early = employed_month(replace(state, turn=months - 1), loaded.balance, loaded.game_data)
    rec = dict(early.reveal(1, person.id).attributes)  # type: ignore[union-attr]
    assert any(rec[k].hw > 0 for k in KEYS)  # not yet: still ranges
    later = employed_month(replace(state, turn=months), loaded.balance, loaded.game_data)
    reveal = later.reveal(1, person.id)
    assert reveal is not None
    for key in KEYS:
        low, high = revealed_range(person, reveal, key)
        assert low == high == round(person.skills[key])  # one value, the true one
    others = [rec for key, rec in reveal.attributes if key not in KEYS and key != "pa"]
    assert any(r.hw > 0 for r in others)  # only those three
