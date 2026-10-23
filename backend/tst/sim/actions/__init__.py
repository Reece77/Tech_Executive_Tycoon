"""Immediate player actions (ADR-0014).

`apply_action` is pure: it takes the state between turns and returns the new state, any
ledger entries and log items, all belonging to `state.turn`. Randomness inside an action
uses stream `actions` keyed by the action's `seq` within the turn (ADR-0013).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from tst.sim.actions.hiring import (
    CloseSearch,
    Fire,
    HiringAction,
    Interview,
    MakeOffer,
    OpenSearch,
    ReferenceCheck,
    WithdrawOffer,
    check_candidate,
    close_search,
    fire,
    make_offer,
    open_search,
    withdraw_offer,
)
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.ledger import LedgerBalances, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

type Action = HiringAction

ACTION_TYPES: dict[str, type[Any]] = {
    "open_search": OpenSearch,
    "close_search": CloseSearch,
    "interview": Interview,
    "reference_check": ReferenceCheck,
    "make_offer": MakeOffer,
    "withdraw_offer": WithdrawOffer,
    "fire": Fire,
}

__all__ = [
    "ACTION_TYPES",
    "Action",
    "ActionResult",
    "CloseSearch",
    "Fire",
    "Interview",
    "MakeOffer",
    "OpenSearch",
    "ReferenceCheck",
    "WithdrawOffer",
    "action_from_payload",
    "action_payload",
    "apply_action",
]


@dataclass(frozen=True, slots=True)
class ActionResult:
    new_state: GameState
    ledger_entries: tuple[LedgerEntry, ...]
    log_items: tuple[LogItem, ...]


def apply_action(
    state: GameState,
    action: Action,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    ledger_balances: LedgerBalances,
    *,
    seq: int,
) -> ActionResult:
    """Apply one action. Raises a domain error, changing nothing, if it is not allowed."""
    match action:
        case OpenSearch():
            out = open_search(state, action, balance, data, ledger_balances)
        case CloseSearch():
            out = close_search(state, action)
        case Interview():
            out = check_candidate(
                state, action.actor_id, action.candidate_id, "interview", rng, seq, balance, data
            )
        case ReferenceCheck():
            out = check_candidate(
                state,
                action.actor_id,
                action.candidate_id,
                "reference_check",
                rng,
                seq,
                balance,
                data,
            )
        case MakeOffer():
            out = make_offer(state, action, balance)
        case WithdrawOffer():
            out = withdraw_offer(state, action)
        case Fire():
            out = fire(state, action, balance)
    return ActionResult(new_state=out.state, ledger_entries=out.entries, log_items=out.log)


def action_payload(action: Action) -> dict[str, Any]:
    """JSON-ready fields of an action, including its `kind` (stored in decision_log)."""
    return asdict(action)


def action_from_payload(payload: dict[str, Any]) -> Action:
    kind = payload.get("kind")
    cls = ACTION_TYPES.get(str(kind))
    if cls is None:
        raise InvalidActionError(f"unknown action kind {kind!r}")
    action: Action = cls(**payload)
    return action
