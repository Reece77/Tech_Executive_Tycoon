"""M15b sub-task 6 (formulas.md 30.5): each stop condition stops the loop, the loop stops after
a year at most, and it decides nothing (what it stops for is still waiting)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.events.models import GameEvent
from tst.sim.mna.models import Deal
from tst.sim.modes.continue_until import needs_player
from tst.sim.org.models import Pitch, Proposal
from tst.sim.press.models import Promise
from tst.sim.state import GameState


def _event(state: GameState, severity: str) -> GameEvent:
    return GameEvent(
        1,
        1,
        state.turn,
        "x",
        "personnel",
        severity,
        "t",
        1.0,
        status="open",  # type: ignore[arg-type]
    )


def _pitch(state: GameState) -> Pitch:
    return Pitch(
        1,
        1,
        "cto",
        2,
        state.turn,
        "new_product",
        (),
        "t",
        "w",
        1,
        0,
        0,
        0,
        "customers",
        0,
        1,
        "low",
    )  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda s: replace(s, save_meta=replace(s.save_meta, game_state="bankrupt")), "game_over"),
        (lambda s: replace(s, events=(_event(s, "critical"),)), "critical_event"),
        (lambda s: replace(s, events=(_event(s, "major"),)), "event"),
        (lambda s: replace(s, pitches=(_pitch(s),)), "pitch"),
        (
            lambda s: replace(s, proposals=(Proposal(1, 1, "cfo", 2, s.turn, "loan", (), "t"),)),  # type: ignore[arg-type]
            "proposal",
        ),
        (lambda s: replace(s, promises=(Promise(1, 1, "ship", s.turn, s.turn + 1),)), "promise"),
        (
            lambda s: replace(s, deals=(Deal(1, 1, 5, 10**9, 1.0, s.turn, status="blocked"),)),
            "deal",
        ),
    ],
)
def test_each_stop_condition_stops_it(loaded: LoadedData, change, reason: str) -> None:  # type: ignore[no-untyped-def]
    state = fresh_game(loaded)
    assert needs_player(state) is None
    assert needs_player(change(state)) == reason


def test_what_does_not_need_the_player(loaded: LoadedData) -> None:
    s = fresh_game(loaded)
    assert needs_player(replace(s, events=(_event(s, "minor"),))) is None  # minor: Continue
    assert needs_player(replace(s, promises=(Promise(1, 1, "ship", s.turn, s.turn + 6),))) is None
    review = Deal(1, 1, 5, 10**9, 1.0, s.turn, status="review")
    assert needs_player(replace(s, deals=(review,))) is None


def test_the_loop_plays_a_year_at_most_and_decides_nothing(
    tmp_path: Path, loaded: LoadedData
) -> None:
    from tests.helpers import fund_save
    from tst.db.repository import continue_until, create_save, read_session, read_state

    path = create_save(
        "cu", 3, "funded_spinout", company_name="Kestrel", data=loaded, save_dir=tmp_path
    )
    fund_save(path, 10**12)
    played, why = continue_until(path, loaded, max_months=3)
    with read_session(path) as session:
        state = read_state(session)
    assert played <= 3 and (why == "months") == (played == 3)
    assert state.turn == played
    if why != "months":  # whatever stopped it is still waiting for the player
        assert needs_player(state) == why
