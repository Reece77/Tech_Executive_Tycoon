"""M43r finding 14 (Codex review 9): the pre-2040 guard is a same-code differential.

52.5 target 1 keeps its mode-parity check against the recorded digests and adds a replay on the
same code against a reference arm with M37's rules disabled (dynasty.start_year moved past the
horizon), so a rule moved before January 2040 shows even when both settings share it. The
mutation here moves one M37 rule (rival leaders' handovers and short markets' entrants, 52.3) a
year early; the replay names January 2039, its first differing month."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game
from tst.balance import m37
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.dynasty import mode
from tst.sim.dynasty import rivals as dynasty_rivals
from tst.sim.ledger import CASH, COMMON_EQUITY
from tst.sim.state import GameState

JAN_2039 = ym_to_turn(2039, 1)
MONTHS = 12  # January to December 2039


FUNDS = 10**13  # the player's cash, so the year plays through


def _start(loaded: LoadedData) -> GameState:
    return replace(fresh_game(loaded, seed=2), turn=JAN_2039)


def _replay(loaded: LoadedData) -> tuple[list[str], list[str]]:
    state = _start(loaded)
    funded = {(state.player.id, CASH): FUNDS, (state.player.id, COMMON_EQUITY): -FUNDS}
    return m37.replay_pair(state, MONTHS, loaded, m37.reference_loaded(), funded)


def test_the_reference_arm_has_m37_past_the_horizon(loaded: LoadedData) -> None:
    ref = m37.reference_loaded()
    b = loaded.balance.dynasty
    assert ref.balance.dynasty.start_year == b.start_year + m37.REFERENCE_SHIFT
    assert ref.balance.dynasty.end_year == b.end_year + m37.REFERENCE_SHIFT
    assert mode.start_turn(ref.balance) > ym_to_turn(2069, 12)


def test_unchanged_code_replays_2039_identically(loaded: LoadedData) -> None:
    a, b = _replay(loaded)
    assert len(a) == MONTHS
    assert m37.first_differing_turn(JAN_2039, a, b) is None


def test_a_rule_moved_across_january_2040_is_caught_at_its_first_month(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    def a_year_early(state: GameState, balance) -> bool:  # type: ignore[no-untyped-def]
        return state.turn >= mode.start_turn(balance) - 12

    monkeypatch.setattr(dynasty_rivals, "in_dynasty_years", a_year_early)
    a, b = _replay(loaded)
    assert len(a) == MONTHS
    assert m37.first_differing_turn(JAN_2039, a, b) == JAN_2039


def test_differential_names_the_first_differing_month() -> None:
    runs = {"steady/1/standard": ["a", "b", "c"], "steady/1/dynasty": ["a", "x", "c"]}
    diff = m37.differential(runs, {"steady/1": ["a", "b", "c"]})
    assert diff["steady/1/standard"] is None
    assert diff["steady/1/dynasty"] is not None and "1" in diff["steady/1/dynasty"]
