"""Answering an event (docs/formulas.md 16.3; ADR-0014): an immediate action at energy 0.
The chosen effects apply at once; Continue answers what is left (minor and major only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import EventError
from tst.sim.events.effects import apply_choice
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class ChooseEvent:
    actor_id: int
    event_id: int
    choice: str
    kind: Literal["choose_event"] = "choose_event"


def choose_event(
    state: GameState, action: ChooseEvent, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    event = state.event(action.event_id)
    if event is None or event.company_id != company:
        raise EventError(f"no event {action.event_id}")
    if event.status != "open" or event.turn > state.turn:
        raise EventError(f"event {action.event_id} is not waiting for an answer")
    if event.choice(action.choice) is None:
        raise EventError(f"event {action.event_id} has no choice {action.choice!r}")
    state = spend_energy(state, action.actor_id, "choose_event", balance)
    state, entries, logs = apply_choice(state, event, action.choice, balance, data, auto=False)
    return Outcome(state, entries, logs)
