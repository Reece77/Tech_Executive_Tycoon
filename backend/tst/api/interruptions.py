"""Interruptions (docs/formulas.md 42.4; M29): which severities stop Continue and Holiday.

Critical always stops and minor never does (23.1); `stop_on` in the UI settings says whether
major events stop the player's Continue too (the default) and is a holiday's default stop.
With `stop_on: critical`, Continue first answers each open major event with its first choice:
exactly what phase 1 does with an unanswered major event when the player is not at the
controls (16.3). The simulation's rules are unchanged; only who presses the button differs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from tst.db import repository
from tst.loader import LoadedData
from tst.sim.actions import ChooseEvent
from tst.sim.events.effects import blocking_events
from tst.sim.state import GameState
from tst.ui_settings import load_ui

type StopOn = Literal["major", "critical"]


def stop_on(save_dir: Path) -> StopOn:
    return load_ui(save_dir).onboarding.stop_on


def stops(severity: str, level: StopOn) -> bool:
    return severity == "critical" or (severity == "major" and level == "major")


def blocking_ids(state: GameState, level: StopOn) -> list[int]:
    """The open events that stop Continue under this setting."""
    return [e.id for e in blocking_events(state) if stops(e.severity, level)]


def answer_waived(path: Path, data: LoadedData, level: StopOn) -> int:
    """Answer the open major events that do not stop Continue with their first choice, so the
    turn can run (the same choice phase 1 makes on a holiday). Returns how many."""
    if level == "major":
        return 0
    answered = 0
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    founder = state.founder_of(state.player.id)
    if founder is None:
        return 0
    for event in blocking_events(state):
        if event.severity == "major" and event.choices:
            repository.run_action(
                path, data, ChooseEvent(founder.id, event.id, event.choices[0].key)
            )
            answered += 1
    return answered
