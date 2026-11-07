"""Continue until something needs me (docs/formulas.md 30.5, M15b sub-task 6): what stops the
loop. Unlike Holiday it delegates nothing: the loop plays months as Continue does and stops,
before the next month, on the first of these, decisions left waiting in the inbox."""

from __future__ import annotations

from typing import Final, Literal

from tst.sim.events.effects import blocking_events
from tst.sim.state import GameState

MAX_MONTHS: Final = 12  # tunable-exempt: 30.5 defines the loop's limit as a year

type StopReason = Literal[
    "game_over", "critical_event", "event", "pitch", "proposal", "promise", "deal", "months"
]

LABELS: Final[dict[str, str]] = {
    "game_over": "the game is over",
    "critical_event": "a critical event needs an answer",
    "event": "an event needs an answer",
    "pitch": "a pitch above your auto-approve limit waits for you",
    "proposal": "an executive's proposal waits for you",
    "promise": "a promise comes due",
    "deal": "a deal waits for your decision",
    "months": "a year has passed",
}


def needs_player(state: GameState) -> StopReason | None:
    """The first thing that needs the player now, or None."""
    if state.save_meta.game_state != "active":
        return "game_over"
    cid = state.player.id
    blocking = blocking_events(state)
    if any(e.severity == "critical" for e in blocking):
        return "critical_event"
    if blocking:
        return "event"
    if state.pending_pitches(cid):  # pending: above the limit, so not auto-approved (27.1)
        return "pitch"
    if state.pending_proposals(cid):
        return "proposal"
    if any(
        p.company_id == cid and p.status == "open" and p.deadline_turn <= state.turn + 1
        for p in state.promises
    ):
        return "promise"
    if any(d.acquirer_id == cid and d.status == "blocked" for d in state.deals):
        return "deal"  # a remedy to accept or a deal to abandon (28.4)
    return None
