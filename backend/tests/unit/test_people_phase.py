"""Turn phase 8: growth and aging for everyone on staff (formulas.md section 3)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tst.loader import LoadedData
from tst.sim.decisions import Decisions
from tst.sim.ledger import CASH
from tst.sim.people.founder import FounderSpec
from tst.sim.people.generator import generate_person
from tst.sim.people.growth import grow_person
from tst.sim.people.models import current_ability
from tst.sim.rng import RngFactory
from tst.sim.scale import ATTR_MAX, ATTR_MIN
from tst.sim.setup import DEFAULT_FOUNDER, PLAYER_COMPANY_ID, new_game
from tst.sim.state import GameState
from tst.sim.turn import advance_turn


def start(loaded: LoadedData, seed: int, founder: FounderSpec = DEFAULT_FOUNDER) -> GameState:
    scenario = loaded.game_data.scenario("garage_bootstrap")
    assert scenario is not None
    state, _ = new_game(
        save_name="t",
        master_seed=seed,
        scenario=scenario,
        difficulty="standard",
        company_name="Co",
        founder=founder,
        balance=loaded.balance,
        data=loaded.game_data,
    )
    return state


def play(loaded: LoadedData, state: GameState, turns: int) -> list[GameState]:
    rng = RngFactory(state.save_meta.master_seed)
    states = [state]
    balances = {(PLAYER_COMPANY_ID, CASH): 10**12}
    for _ in range(turns):
        result = advance_turn(
            states[-1], Decisions(), rng, loaded.balance, loaded.game_data, balances
        )
        states.append(result.new_state)
    return states


def test_headcount_is_one_from_turn_0(loaded: LoadedData) -> None:
    state = start(loaded, 1)
    result = advance_turn(state, Decisions(), RngFactory(1), loaded.balance, loaded.game_data, {})
    assert result.snapshot.turn == 0
    assert result.snapshot.for_company(PLAYER_COMPANY_ID).headcount == 1


def test_growth_is_seeded_and_deterministic(loaded: LoadedData) -> None:
    a = play(loaded, start(loaded, 5), 12)[-1]
    b = play(loaded, start(loaded, 5), 12)[-1]
    assert a.people == b.people
    assert a.people[0].skills != start(loaded, 5).people[0].skills
    assert a.people[0].potential_ability == start(loaded, 5).people[0].potential_ability


def test_skills_stay_in_range(loaded: LoadedData) -> None:
    for state in play(loaded, start(loaded, 9), 60):
        for _, value in state.people[0].skills.items:
            assert ATTR_MIN <= value <= ATTR_MAX


def test_only_staff_grow(loaded: LoadedData) -> None:
    state = start(loaded, 2)
    gen = RngFactory(2).stream(0, "misc", 1)
    stranger = generate_person(
        gen,
        loaded.game_data,
        loaded.balance,
        0,
        loaded.game_data.role("designer"),
        "junior",
        "europe",
        person_id=2,
    )
    state = replace(state, people=(*state.people, stranger))
    after = play(loaded, state, 3)[-1]
    assert after.person(2) == stranger
    assert after.person(1) != state.person(1)


def test_growth_noise_is_keyed_by_person(loaded: LoadedData) -> None:
    """A person's growth does not depend on who else exists (ADR-0013)."""
    founder = start(loaded, 4).people[0]
    alone = grow_person(founder, 3, RngFactory(4), loaded.game_data, loaded.balance)
    rng = RngFactory(4)
    for other in range(2, 30):
        grow_person(replace(founder, id=other), 3, rng, loaded.game_data, loaded.balance)
    assert grow_person(founder, 3, rng, loaded.game_data, loaded.balance) == alone


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_young_founder_grows_and_old_founder_does_not(loaded: LoadedData, seed: int) -> None:
    """Acceptance: over 120 turns a 24-year-old's CA rises; a 58-year-old's is flat or falls."""
    data = loaded.game_data
    young = play(loaded, start(loaded, seed, FounderSpec("engineer", age=24)), 120)
    old = play(loaded, start(loaded, seed, FounderSpec("engineer", age=58)), 120)

    young_ca = [current_ability(s.people[0], data) for s in young]
    old_ca = [current_ability(s.people[0], data) for s in old]
    assert young_ca[-1] > young_ca[0] + 5
    assert old_ca[-1] <= old_ca[0]
    assert young[-1].people[0].age(120) == 34
