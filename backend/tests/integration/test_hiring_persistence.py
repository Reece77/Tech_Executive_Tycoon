"""M1b state and persistence: mission, id counters, searches, candidates, offers, energy."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import select, text

from tst.db import migrate
from tst.db.models import CandidateRow, OfferRow, SearchRow
from tst.db.repository import create_save, open_session
from tst.db.session import make_engine
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.errors import InvalidMissionError
from tst.sim.hiring.models import Candidate, NextIds, Offer, PersonState, Search
from tst.sim.people.generator import generate_person
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import GameState, with_candidate, with_offer, with_person, with_search


def fresh(loaded: LoadedData, mission: tuple[str, ...] | None = None) -> GameState:
    scenario = loaded.game_data.scenario("ex_big_tech_founders")
    assert scenario is not None
    state, _ = new_game(
        save_name="t",
        master_seed=3,
        scenario=scenario,
        difficulty="standard",
        company_name="Co",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
        mission=mission,
    )
    return state


def test_new_game_mission_defaults_to_founders_interests(loaded: LoadedData) -> None:
    state = fresh(loaded)
    founder = state.people[0]
    order = loaded.game_data.interest_keys
    expected = tuple(sorted(founder.interests, key=order.index)[:2])
    assert state.player.mission == expected
    assert len(state.player.mission) == 2


def test_new_game_mission_given(loaded: LoadedData) -> None:
    assert fresh(loaded, ("enterprise", "ai")).player.mission == ("enterprise", "ai")


@pytest.mark.parametrize(
    ("mission", "message"),
    [
        (("ai",), "exactly 2 different interests"),
        (("ai", "ai"), "exactly 2 different interests"),
        (("ai", "fintech", "gaming"), "exactly 2 different interests"),
        (("ai", "knitting"), "unknown mission interests ['knitting']"),
    ],
)
def test_new_game_mission_invalid(
    loaded: LoadedData, mission: tuple[str, ...], message: str
) -> None:
    with pytest.raises(InvalidMissionError, match=message.replace("[", r"\[").replace("]", r"\]")):
        fresh(loaded, mission)


def test_new_game_energy_and_counters(loaded: LoadedData) -> None:
    state = fresh(loaded)
    assert state.person_state(1) == PersonState(person_id=1, energy=100)
    assert state.next_ids == NextIds(person=2, search=1, offer=1, employment=2)


def _with_hiring(loaded: LoadedData, state: GameState) -> GameState:
    """A state with one open search, two candidates and a pending offer."""
    gen = RngFactory(9).stream(0, "misc", 1)
    role = loaded.game_data.role("software_engineer")
    for pid in (2, 3):
        person = generate_person(
            gen, loaded.game_data, loaded.balance, 0, role, "mid", "europe", person_id=pid
        )
        state = with_person(state, person)
        state = with_candidate(
            state,
            Candidate(
                person_id=pid,
                company_id=1,
                search_id=1,
                channel="job_post",
                created_turn=0,
                expires_turn=3,
            ),
        )
    state = with_search(
        state, Search(1, 1, "software_engineer", "job_post", actor_id=1, opened_turn=0)
    )
    state = with_offer(
        state, Offer(1, 1, 2, actor_id=1, salary_cents=9_000_000, equity_bp=50, made_turn=0)
    )
    return replace(state, next_ids=NextIds(person=4, search=2, offer=2, employment=2))


def test_hiring_state_round_trips(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "h", 3, "ex_big_tech_founders", company_name="Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        before = load_state(session)
        after = _with_hiring(loaded, before)
        sync_state(session, before, after)
    with open_session(path) as session:
        loaded_back = load_state(session)
    assert loaded_back.searches == after.searches
    assert loaded_back.candidates == after.candidates
    assert loaded_back.offers == after.offers
    assert loaded_back.people == after.people
    assert loaded_back.next_ids == after.next_ids
    assert loaded_back.person_states == after.person_states
    assert loaded_back.player.mission == after.player.mission


def test_only_live_records_load(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "live", 3, "ex_big_tech_founders", company_name="Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        base = load_state(session)
        live = _with_hiring(loaded, base)
        sync_state(session, base, live)
    with open_session(path) as session, session.begin():
        live = load_state(session)
        done = with_offer(live, replace(live.offers[0], status="declined", resolved_turn=1))
        done = with_candidate(done, replace(done.candidates[0], status="declined", resolved_turn=1))
        done = with_search(done, replace(done.searches[0], status="closed", closed_turn=1))
        sync_state(session, live, done)
    with open_session(path) as session:
        state = load_state(session)
        assert [c.person_id for c in state.candidates] == [3]
        assert [p.id for p in state.people] == [1, 3]
        assert state.offers == () and state.searches == ()
        # The rows stay in the database with their status.
        assert session.scalar(select(CandidateRow.status).where(CandidateRow.person_id == 2)) == (
            "declined"
        )
        assert session.scalar(select(OfferRow.status)) == "declined"
        assert session.scalar(select(SearchRow.status)) == "closed"


def test_upgrade_from_0002_sets_counters_mission_and_energy(
    tmp_path: Path, loaded: LoadedData
) -> None:
    path = create_save(
        "old", 3, "garage_bootstrap", company_name="Co", data=loaded, save_dir=tmp_path
    )
    migrate.downgrade(path, "0002_people")
    engine = make_engine(path)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM person_state"))  # M1a saves had none
    engine.dispose()

    backup = migrate.ensure_current(path)
    assert backup is not None
    with open_session(path) as session:
        state = load_state(session)
    assert state.player.mission == ()
    assert state.next_ids == NextIds(person=2, search=1, offer=1, employment=2)
    assert state.person_state(1).energy == 100
