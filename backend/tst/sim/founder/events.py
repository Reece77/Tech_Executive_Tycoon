"""Queueing M24's engine events (trigger founder_life, data/events/founder.yaml)."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.events.models import QueuedEvent
from tst.sim.state import GameState, with_queued


def queue(state: GameState, company_id: int, template: str, due: int) -> GameState:
    qid, ids = state.next_ids.take("queued")
    return with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid, company_id=company_id, template_id=template, due_turn=due, source_event_id=None
        ),
    )
