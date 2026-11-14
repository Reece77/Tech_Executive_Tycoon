"""M29 (formulas.md 42.1-42.3): unlock conditions, Getting started and What next, on fixtures."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game, with_product
from tst.loader import LoadedData
from tst.sim import unlocks
from tst.sim.exploration.models import DeskStudy, Project
from tst.sim.state import GameState, with_company
from tst.sim.whatnext import MAX_ITEMS, what_next

ALWAYS = {s.key for s in unlocks.SYSTEMS if s.always}
CASH = 10**9


def at_stage(state: GameState, stage: int) -> GameState:
    return with_company(state, replace(state.player, stage=stage))


def test_a_new_game_shows_only_the_stage_one_screens(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    assert set(unlocks.conditions(state, loaded.balance, loaded.game_data)) == ALWAYS


def test_stages_open_screens(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    b, d = loaded.balance, loaded.game_data
    expect = {
        2: {"offices", "research", "rankings"},
        3: {"offices", "research", "rankings", "infrastructure", "hardware", "automation"},
        4: {
            "offices",
            "research",
            "rankings",
            "infrastructure",
            "hardware",
            "refineries",
            "fabs",
            "automation",  # M27a: the Automation screen opens at stage 3 (40.8)
        },
    }
    for stage, keys in expect.items():
        got = set(unlocks.conditions(at_stage(state, stage), b, d)) - ALWAYS
        assert got == keys, stage
    assert "group" in unlocks.conditions(at_stage(state, 5), b, d)


def test_facts_open_screens_before_their_stage(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    b, d = loaded.balance, loaded.game_data
    chip = with_product(state, category="chips_mobile_soc", status="in_development", root=False)
    assert "fabs" in unlocks.conditions(chip, b, d)
    assert "is a chip product" in unlocks.conditions(chip, b, d)["fabs"]
    device = with_product(state, category="devices", status="in_development", root=False)
    assert "hardware" in unlocks.conditions(device, b, d)
    study = DeskStudy(1, state.player.id, "north_america", "copper", 0, 3, 1.0)
    explored = replace(state, desk_studies=(study,))
    assert unlocks.conditions(explored, b, d)["exploration"] == "the group ran a desk study"
    project = Project(1, state.player.id, "north_america", 0, 0, 60)
    licensed = replace(state, projects=(project,))
    assert "exploration" in unlocks.conditions(licensed, b, d)
    assert "mines" not in unlocks.conditions(licensed, b, d)
    feasible = replace(state, projects=(replace(project, level="scoping"),))
    assert "mines" in unlocks.conditions(feasible, b, d)


def test_unlocks_are_announced_once_and_not_for_old_saves(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    before = at_stage(fresh_game(loaded), 1)
    after = at_stage(before, 2)
    fresh = unlocks.newly_unlocked(before, after, frozenset(), b, d)
    assert {s.key for s, _ in fresh} == {"offices", "research", "rankings"}
    assert all(reason == "the company reached stage 2" for _, reason in fresh)
    # announced already: nothing new
    assert (
        unlocks.newly_unlocked(before, after, frozenset({"offices", "research", "rankings"}), b, d)
        == ()
    )
    # a save from before M29 already at stage 2: its screens show without an item
    assert unlocks.newly_unlocked(after, after, frozenset(), b, d) == ()


@settings(max_examples=30, deadline=None)
@given(low=st.integers(0, 5), high=st.integers(0, 5))
def test_a_higher_stage_never_hides_a_screen(low: int, high: int, loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    b, d = loaded.balance, loaded.game_data
    lo, hi = sorted((low, high))
    assert set(unlocks.conditions(at_stage(state, lo), b, d)) <= set(
        unlocks.conditions(at_stage(state, hi), b, d)
    )


def test_system_ids_are_unique_and_stable() -> None:
    assert len({s.id for s in unlocks.SYSTEMS}) == len(unlocks.SYSTEMS)
    assert len({s.key for s in unlocks.SYSTEMS}) == len(unlocks.SYSTEMS)
    # stored in unlock inbox items: these must never change
    assert unlocks.BY_KEY["exploration"].id == 15 and unlocks.BY_KEY["world"].id == 21
    assert set(unlocks.CHECKS) == {s.key for s in unlocks.SYSTEMS if not s.always}


def test_getting_started_ticks_from_state(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = fresh_game(loaded)
    steps = unlocks.getting_started(state, b, d)
    assert [s.key for s in steps] == [k for k, *_ in unlocks.STEP_TEXT]
    assert not any(s.done for s in steps)
    assert unlocks.first_year(state)
    live = with_product(state, status="live")
    done = {s.key for s in unlocks.getting_started(live, b, d) if s.done}
    assert {"product_team", "launch_bars", "launch"} <= done
    assert "seed_round" not in done
    assert not unlocks.first_year(replace(state, turn=state.player.founded_turn + 12))


def test_what_next_is_short_and_shows_unlocks(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = fresh_game(loaded)
    items = what_next(state, CASH, b, d, [unlocks.BY_KEY["offices"]])
    assert len(items) <= MAX_ITEMS
    guide = [i for i in items if i.key == "unlock"]
    assert guide and guide[0].link_kind == "guide" and guide[0].link_key == "offices"
    many = what_next(state, CASH, b, d, list(unlocks.SYSTEMS))
    assert len(many) == MAX_ITEMS
