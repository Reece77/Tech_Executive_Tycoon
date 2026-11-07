"""Rival CEO profiles (M15b addendum 11): appearances reveal a little, approaches and
diligence more; ranges only, never true values."""

from __future__ import annotations

from dataclasses import replace

from tests.helpers import fresh_game
from tst.api.press_views import ceo_profile
from tst.loader import LoadedData
from tst.sim.hiring.models import Search
from tst.sim.mna.models import TargetFile
from tst.sim.people.models import PA_KEY
from tst.sim.press.models import Statement
from tst.sim.press.names import rival_ceo_id
from tst.sim.rivals.ceo_knowledge import ceo_knowledge_month, learn_of_ceo, month_events
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

SEED = 7


def _rival_and_ceo(state: GameState) -> tuple[int, int]:
    for r in state.rivals():
        ceo = rival_ceo_id(state, r.id)
        if ceo is not None:
            return r.id, ceo
    raise AssertionError("no rival with a CEO")


def _mean_hw(state: GameState, ceo: int, loaded: LoadedData) -> float:
    reveal = state.reveal(state.player.id, ceo)
    assert reveal is not None
    keys = set(loaded.game_data.skill_keys)
    widths = [r.hw for k, r in reveal.attributes if k in keys]
    return sum(widths) / len(widths)


def test_appearances_reveal_a_little_and_diligence_more(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    _, ceo = _rival_and_ceo(state)
    rng = RngFactory(SEED)
    b, d = loaded.balance, loaded.game_data
    seen = learn_of_ceo(state, ceo, "public_appearance", rng, b, d)
    approached = learn_of_ceo(state, ceo, "rival_approach", rng, b, d)
    studied = learn_of_ceo(state, ceo, "rival_diligence", rng, b, d)
    stranger = _mean_hw(state, ceo, loaded)  # rivals' key people start known as strangers
    assert stranger == b.reveal.initial_hw.skill
    assert stranger > _mean_hw(seen, ceo, loaded) > _mean_hw(approached, ceo, loaded)
    assert _mean_hw(approached, ceo, loaded) > _mean_hw(studied, ceo, loaded)
    # an appearance says nothing of potential
    pa = seen.reveal(state.player.id, ceo)
    before = state.reveal(state.player.id, ceo)
    assert (
        pa is not None and before is not None and pa.record(PA_KEY).hw == before.record(PA_KEY).hw
    )


def test_month_events_and_phase(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    rival, ceo = _rival_and_ceo(state)
    player = state.player.id
    state = replace(
        state,
        statements=(Statement(1, rival, ceo, state.turn, "statement", "Hello."),),
        searches=(
            Search(
                id=9,
                company_id=player,
                role="engineer",
                channel="poach",
                actor_id=0,
                opened_turn=state.turn,
                rival_id=rival,
            ),
        ),
        target_files=(
            TargetFile(acquirer_id=player, target_id=rival, diligence_done_turn=state.turn),
        ),
    )
    assert month_events(state) == [
        (ceo, "public_appearance"),
        (ceo, "rival_approach"),
        (ceo, "rival_diligence"),
    ]
    after = ceo_knowledge_month(state, RngFactory(SEED), loaded.balance, loaded.game_data)
    again = ceo_knowledge_month(state, RngFactory(SEED), loaded.balance, loaded.game_data)
    assert after.reveal(player, ceo) == again.reveal(player, ceo)  # seeded
    assert _mean_hw(after, ceo, loaded) < loaded.balance.reveal.initial_hw.skill


def test_profile_shows_ranges_never_true_values(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    _, ceo = _rival_and_ceo(state)
    assert ceo_profile(state, None, loaded) is None  # no CEO
    state = learn_of_ceo(
        state, ceo, "public_appearance", RngFactory(SEED), loaded.balance, loaded.game_data
    )
    profile = ceo_profile(state, ceo, loaded)
    assert profile is not None
    person = state.person(ceo)
    dumped = profile.model_dump_json()
    assert "potential_ability" not in dumped and "true" not in dumped
    for attr in profile.skills:
        assert attr.range.max - attr.range.min >= 2  # still a range, not the value
        assert attr.range.min <= person.skills[attr.key] + 1  # contains (or near) the truth
    assert len(profile.personality) == len(loaded.game_data.personality)
    assert profile.learned_label
