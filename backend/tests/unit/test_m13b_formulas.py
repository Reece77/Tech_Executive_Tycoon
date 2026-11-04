"""M13b sub-task 1 (formulas.md 27.1-27.3): the pitch probability, the quality rule, the case
spread, the auto-approve rule, decline morale, the stronger first-mover keys, the `pitch`
stream and the report voices."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.org.formulas import (
    auto_approve_limit,
    auto_approves,
    case_spread,
    decision_quality,
    decline_morale,
    pitch_chance,
    pitch_pick,
)
from tst.sim.org.voices import voice_for
from tst.sim.people.reveal import revealed_range
from tst.sim.rng import STREAM_IDS


def test_pitch_chance(loaded: LoadedData) -> None:
    """clamp(0.45 + 0.04 (ambition - 10), 0.15, 0.9) (27.1)."""
    pb = loaded.balance.pitch
    assert pitch_chance(10, pb) == pytest.approx(0.45)
    assert pitch_chance(15, pb) == pytest.approx(0.65)
    assert pitch_chance(5, pb) == pytest.approx(0.25)
    assert pitch_chance(20, pb) == pytest.approx(0.85)
    assert pitch_chance(1, pb) == pytest.approx(0.15)  # 0.09 clamped up
    assert pitch_chance(1, pb.model_copy(update={"per_ambition": 1.0})) == 0.15
    assert pitch_chance(20, pb.model_copy(update={"per_ambition": 1.0})) == 0.9


@given(ambition=st.floats(1, 20))
def test_pitch_chance_bounds(loaded: LoadedData, ambition: float) -> None:
    lo, hi = loaded.balance.pitch.chance_clamp
    assert lo <= pitch_chance(ambition, loaded.balance.pitch) <= hi


def test_quality_rule(loaded: LoadedData) -> None:
    """The best candidate with probability clamp(0.55 + 0.03 s, 0.6, 0.98), else the second
    best (27.1, 24.2)."""
    q = loaded.balance.exec_authority.quality
    assert decision_quality(15, q) == pytest.approx(0.98)  # 0.55 + 0.45 = 1.0, capped
    assert decision_quality(8, q) == pytest.approx(0.79)
    assert pitch_pick(0, 0.1, 0.9) is None
    assert pitch_pick(3, 0.5, 0.79) == 0
    assert pitch_pick(3, 0.8, 0.79) == 1
    assert pitch_pick(1, 0.99, 0.6) == 0  # one candidate: it is the best and the second best


def test_case_spread_from_displayed_score(loaded: LoadedData) -> None:
    pb = loaded.balance.pitch
    assert case_spread(0, pb) == pytest.approx(0.6)
    assert case_spread(8, pb) == pytest.approx(0.4)
    assert case_spread(15, pb) == pytest.approx(0.225)
    assert case_spread(20, pb) == pytest.approx(0.15)  # the floor
    assert case_spread(8, pb) > case_spread(15, pb)  # weaker-looking, wider


def test_auto_approve_rule(loaded: LoadedData) -> None:
    """Default 5% of cash; 0 always asks; only on Holiday; strictly under the limit (27.1)."""
    pb = loaded.balance.pitch
    assert auto_approve_limit(10_000_000_00, None, pb) == 50_000_000
    assert auto_approve_limit(-5, None, pb) == 0
    assert auto_approve_limit(10_000_000_00, 123, pb) == 123
    assert auto_approve_limit(10_000_000_00, 0, pb) == 0
    assert auto_approves(49_999_999, 50_000_000, on_holiday=True)
    assert not auto_approves(50_000_000, 50_000_000, on_holiday=True)
    assert not auto_approves(1, 50_000_000, on_holiday=False)
    assert not auto_approves(0, 0, on_holiday=True)


def test_decline_morale(loaded: LoadedData) -> None:
    pb = loaded.balance.pitch
    assert decline_morale(10, pb) == 2
    assert decline_morale(14.9, pb) == 2
    assert decline_morale(15, pb) == 4


def test_stronger_first_mover_and_stream(loaded: LoadedData) -> None:
    rnd = loaded.balance.rnd
    # 27.5 target 5 (product manager, 2026-11-04): the window alone adds 25-60% customers
    assert (rnd.first_mover_months, rnd.first_mover_cap, rnd.first_mover_brand) == (24, 5, 6)
    assert rnd.first_mover_appeal == pytest.approx(1.0)
    assert STREAM_IDS["pitch"] == 36
    assert len(set(STREAM_IDS.values())) == len(STREAM_IDS)


def test_report_voice_follows_displayed_personality(loaded: LoadedData) -> None:
    """The voice comes from a revealed range's midpoint, not the true value (27.2, ADR-0007)."""
    state = fresh_game(loaded)
    voices = loaded.game_data.voices
    assert [v.key for v in voices][-1] == "plain" and voices[-1].rule is None
    person = next(p for p in state.people if not p.is_founder and state.reveal(1, p.id))
    reveal = state.reveal(1, person.id)
    assert reveal is not None

    def shown(p, trait):  # type: ignore[no-untyped-def]
        lo, hi = revealed_range(p, reveal, trait)
        return (lo + hi) / 2

    for trait, value in (("ambition", 20.0), ("ambition", 1.0)):
        changed = replace(person, personality=person.personality.updated({trait: value}))
        s2 = replace(state, people=tuple(changed if p.id == person.id else p for p in state.people))
        v = voice_for(s2, 1, person.id, voices)
        expected = next(
            x for x in voices if x.rule is None or x.rule.matches(shown(changed, x.rule.trait))
        )
        assert v.key == expected.key
