"""Shared builders for M1b tests: a fresh game with candidates and employees."""

from __future__ import annotations

from dataclasses import replace

from tst.loader import LoadedData
from tst.sim.hiring.models import Candidate, PersonState, Search
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment, Person
from tst.sim.people.reveal import new_reveal_state
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import (
    GameState,
    with_candidate,
    with_employment,
    with_person,
    with_person_state,
    with_reveal,
    with_search,
)


def fresh_game(
    loaded: LoadedData,
    seed: int = 3,
    scenario: str = "ex_big_tech_founders",
    mission: tuple[str, ...] | None = None,
) -> GameState:
    scenario_def = loaded.game_data.scenario(scenario)
    assert scenario_def is not None
    state, _ = new_game(
        save_name="t",
        master_seed=seed,
        scenario=scenario_def,
        difficulty="standard",
        company_name="Co",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
        mission=mission,
    )
    return state


def make_person(
    loaded: LoadedData, person_id: int, role: str = "software_engineer", level: str = "mid"
) -> Person:
    gen = RngFactory(person_id).stream(0, "misc", person_id)
    return generate_person(
        gen,
        loaded.game_data,
        loaded.balance,
        0,
        loaded.game_data.role(role),
        level,
        "north_america",
        person_id=person_id,
    )


def with_candidates(
    loaded: LoadedData, state: GameState, count: int, role: str = "software_engineer"
) -> GameState:
    """Add an open job-post search and `count` candidates known as strangers."""
    search_id, ids = state.next_ids.take("search")
    state = with_search(
        state,
        Search(search_id, 1, role, "job_post", actor_id=1, opened_turn=state.turn),
    )
    first, ids = ids.take_many("person", count)
    state = replace(state, next_ids=ids)
    for pid in range(first, first + count):
        person = make_person(loaded, pid, role)
        state = with_person(state, person)
        state = with_candidate(
            state,
            Candidate(
                person_id=pid,
                company_id=1,
                search_id=search_id,
                created_turn=state.turn,
                expires_turn=state.turn + loaded.balance.hiring.candidate_shelf_turns,
            ),
        )
        state = with_reveal(
            state,
            new_reveal_state(
                observer_company_id=1,
                person=person,
                turn=state.turn,
                rng=RngFactory(state.save_meta.master_seed),
                data=loaded.game_data,
                balance=loaded.balance,
            ),
        )
    return state


def with_employee(
    loaded: LoadedData,
    state: GameState,
    person: Person,
    salary_cents: int,
    equity_bp: int = 0,
    morale: float = 65.0,
) -> GameState:
    emp_id, ids = state.next_ids.take("employment")
    state = replace(state, next_ids=ids)
    state = with_person(state, person)
    state = with_employment(
        state,
        Employment(
            id=emp_id,
            person_id=person.id,
            company_id=1,
            role=person.role or "software_engineer",
            level=person.level or "mid",
            salary_cents=salary_cents,
            equity_bp=equity_bp,
            start_turn=state.turn,
            end_turn=None,
            status="active",
        ),
    )
    return with_person_state(state, PersonState(person_id=person.id, morale=morale))
