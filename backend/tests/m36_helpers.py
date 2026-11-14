"""Shared M36 test setup: a game in memory with a family (formulas.md 45)."""

from __future__ import annotations

from dataclasses import replace

from tst.balance.game import Game
from tst.loader import LoadedData
from tst.sim.family.setup import FamilySpec
from tst.sim.founder import personal
from tst.sim.ledger import apply_entries
from tst.sim.people.founder import FounderSpec
from tst.sim.setup import new_game
from tst.sim.state import GameState, family_member, with_family_member


def family_game(
    loaded: LoadedData,
    seed: int = 3,
    *,
    age: int = 30,
    setting: str = "children",
    child_ages: tuple[int, ...] = (2, 5),
    scenario: str = "funded_spinout",
) -> Game:
    state, entries = new_game(
        save_name="m36",
        master_seed=seed,
        scenario=loaded.game_data.scenario(scenario),  # type: ignore[arg-type]
        difficulty="standard",
        company_name="Family Co",
        founder=FounderSpec(background="engineer", age=age),
        balance=loaded.balance,
        data=loaded.game_data,
        family=FamilySpec(setting, child_ages if setting == "children" else ()),
    )
    return Game(loaded, state, apply_entries({}, entries))


def with_cash(state: GameState, person_id: int, cents: int) -> GameState:
    return personal.credit(state, person_id, cents, "secondary", "Test cash")


def hire_child(game: Game, person_id: int, role: str = "product_manager") -> None:
    """A grown child joins the player's company (closeness lifted so they accept)."""
    from tst.sim.family import answers, rules

    m = family_member(game.state, person_id)
    assert m is not None
    game.state = with_family_member(game.state, replace(m, closeness=90.0))
    person = game.state.person(person_id)
    data = game.loaded.game_data
    role_key = next(
        (r.key for r in data.roles if r.founder_fit and rules.roles_match(person, r.key, data)),
        role,
    )
    game.state, _ = answers.offer_job(
        game.state, person_id, 1, role_key, "senior", game.loaded.balance, game.loaded.game_data
    )
    assert game.state.employment_of(person_id) is not None
