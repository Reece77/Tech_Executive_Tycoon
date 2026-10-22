"""Reveal invariants (ADR-0007): ranges contain the true value; hw never increases."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import DATA_DIR
from tst.loader import load_all
from tst.sim.errors import UnknownKnowledgeActionError
from tst.sim.people.formulas import EXACT_HALF_WIDTH, displayed_range
from tst.sim.people.models import PA_KEY, RevealRecord, RevealState
from tst.sim.people.reveal import ACTION_GROUPS, apply_knowledge_action
from tst.sim.scale import ABILITY_MAX, ABILITY_MIN, ATTR_MAX, ATTR_MIN

LOADED = load_all(DATA_DIR)
BALANCE = LOADED.balance
SKILL_KEYS = frozenset(LOADED.game_data.skill_keys)

offsets = st.floats(min_value=-0.5, max_value=0.5)
half_widths = st.floats(min_value=0.0, max_value=60.0)
judgments = st.floats(min_value=1.0, max_value=20.0)
actions = st.sampled_from(sorted(ACTION_GROUPS))


def _contains(lo: int, hi: int, true: float, hw: float) -> bool:
    if hw < EXACT_HALF_WIDTH:  # collapsed to the displayed (rounded) true value
        return lo == hi == round(true)
    return lo <= true <= hi


@given(st.floats(min_value=ATTR_MIN, max_value=ATTR_MAX), half_widths, offsets)
def test_attribute_range_contains_true_value(true: float, hw: float, offset: float) -> None:
    lo, hi = displayed_range(true, hw, offset, ATTR_MIN, ATTR_MAX)
    assert ATTR_MIN <= lo <= hi <= ATTR_MAX
    assert _contains(lo, hi, true, hw)
    assert lo <= round(true) <= hi


@given(st.floats(min_value=ABILITY_MIN, max_value=ABILITY_MAX), half_widths, offsets)
def test_pa_range_contains_true_value(true: float, hw: float, offset: float) -> None:
    lo, hi = displayed_range(true, hw, offset, ABILITY_MIN, ABILITY_MAX)
    assert ABILITY_MIN <= lo <= hi <= ABILITY_MAX
    assert _contains(lo, hi, true, hw)


def _state(offset: float) -> RevealState:
    hw = BALANCE.reveal.initial_hw
    attrs = (
        ("software_engineering", RevealRecord(hw.skill, offset, 0)),
        ("ambition", RevealRecord(hw.personality, offset, 0)),
        (PA_KEY, RevealRecord(hw.pa, offset, 0)),
    )
    return RevealState(1, 1, attrs, None, ())


@settings(max_examples=200)
@given(
    st.lists(st.tuples(actions, judgments), max_size=30),
    offsets,
    st.floats(min_value=ATTR_MIN, max_value=ATTR_MAX),
    st.floats(min_value=ABILITY_MIN, max_value=ABILITY_MAX),
)
def test_actions_never_widen(
    steps: list[tuple[str, float]], offset: float, skill: float, pa: float
) -> None:
    state = _state(offset)
    truth = {"software_engineering": skill, "ambition": skill, PA_KEY: pa}
    bounds = {"software_engineering": (ATTR_MIN, ATTR_MAX), "ambition": (ATTR_MIN, ATTR_MAX)}
    bounds[PA_KEY] = (ABILITY_MIN, ABILITY_MAX)

    def widths(s: RevealState) -> dict[str, tuple[float, int]]:
        out = {}
        for key, rec in s.attributes:
            lo, hi = displayed_range(truth[key], rec.hw, rec.offset, *bounds[key])
            assert _contains(lo, hi, truth[key], rec.hw)
            out[key] = (rec.hw, hi - lo)
        return out

    before = widths(state)
    for turn, (action, judgment) in enumerate(steps, start=1):
        state = apply_knowledge_action(
            state, action, judgment, BALANCE, turn=turn, skill_keys=SKILL_KEYS
        )
        after = widths(state)
        for key in after:
            assert after[key][0] <= before[key][0]  # hw never increases
            assert after[key][1] <= before[key][1]  # with a fixed true value, width never grows
        before = after


def test_action_groups() -> None:
    state = _state(0.0)

    def hws(s: RevealState) -> tuple[float, float, float]:
        return tuple(rec.hw for _, rec in s.attributes)  # type: ignore[return-value]

    start = hws(state)
    screened = apply_knowledge_action(
        state, "job_post_screen", 10, BALANCE, turn=3, skill_keys=SKILL_KEYS
    )
    skill, personality, pa = hws(screened)
    assert skill < start[0] and personality == start[1] and pa < start[2]
    assert screened.record("ambition").last_updated_turn == 0
    assert screened.record("software_engineering").last_updated_turn == 3
    assert screened.profile_revealed_turn is None

    checked = apply_knowledge_action(
        state, "reference_check", 10, BALANCE, turn=3, skill_keys=SKILL_KEYS
    )
    skill, personality, pa = hws(checked)
    assert skill == start[0] and personality < start[1] and pa < start[2]

    for action in ("interview", "network_intro"):
        seen = apply_knowledge_action(state, action, 10, BALANCE, turn=4, skill_keys=SKILL_KEYS)
        assert seen.profile_revealed_turn == 4
        again = apply_knowledge_action(seen, action, 10, BALANCE, turn=5, skill_keys=SKILL_KEYS)
        assert again.profile_revealed_turn == 4  # first reveal sticks


def test_engine_reproduces_worked_example() -> None:
    """formulas.md section 4: 8-18, 8-18, 10-17, then 11-16 after 6 months employed."""
    state = RevealState(1, 1, (("software_engineering", RevealRecord(5.0, 0.2, 0)),), None, ())

    def shown(s: RevealState) -> tuple[int, int]:
        rec = s.record("software_engineering")
        return displayed_range(14.0, rec.hw, rec.offset, ATTR_MIN, ATTR_MAX)

    assert shown(state) == (8, 18)
    state = apply_knowledge_action(
        state, "job_post_screen", 12, BALANCE, turn=1, skill_keys=SKILL_KEYS
    )
    assert shown(state) == (8, 18)
    state = apply_knowledge_action(state, "interview", 12, BALANCE, turn=1, skill_keys=SKILL_KEYS)
    assert shown(state) == (10, 17)
    for turn in range(2, 8):
        state = apply_knowledge_action(
            state, "employed_month", 12, BALANCE, turn=turn, skill_keys=SKILL_KEYS
        )
    assert shown(state) == (11, 16)
    assert round(state.record("software_engineering").hw, 2) == 2.03


def test_unknown_action() -> None:
    with pytest.raises(UnknownKnowledgeActionError):
        apply_knowledge_action(_state(0.0), "stalking", 10, BALANCE, turn=1, skill_keys=SKILL_KEYS)
