"""Immediate actions (ADR-0014), taken by the player between turns or by delegates in
phase 2 (ADR-0015).

`apply_action` is pure: it takes the state and returns the new state, any ledger entries
and log items, all belonging to `state.turn`. Randomness inside a player action uses stream
`actions` keyed by the action's `seq` within the turn (ADR-0013); a delegate passes its own
generator (stream `delegate`).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from tst.sim.actions.hiring import (
    CloseSearch,
    Draws,
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
from tst.sim.actions.org import (
    ClosePlan,
    CreatePlan,
    CreateUnit,
    DissolveUnit,
    GiveRaise,
    MovePerson,
    OrgAction,
    Promote,
    Scout,
    SetLeader,
    SetPolicy,
    UpdatePlan,
    close_plan,
    create_plan,
    create_unit,
    dissolve_unit,
    give_raise,
    move_person,
    promote,
    scout,
    set_leader,
    set_policy,
    update_plan,
)
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.ledger import LedgerBalances, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

type Action = HiringAction | OrgAction

ACTION_TYPES: dict[str, type[Any]] = {
    "open_search": OpenSearch,
    "close_search": CloseSearch,
    "interview": Interview,
    "reference_check": ReferenceCheck,
    "make_offer": MakeOffer,
    "withdraw_offer": WithdrawOffer,
    "fire": Fire,
    "create_unit": CreateUnit,
    "dissolve_unit": DissolveUnit,
    "set_leader": SetLeader,
    "move_person": MovePerson,
    "set_policy": SetPolicy,
    "give_raise": GiveRaise,
    "promote": Promote,
    "create_plan": CreatePlan,
    "update_plan": UpdatePlan,
    "close_plan": ClosePlan,
    "scout": Scout,
}

__all__ = [
    "ACTION_TYPES",
    "Action",
    "ActionResult",
    "ClosePlan",
    "CloseSearch",
    "CreatePlan",
    "CreateUnit",
    "DissolveUnit",
    "Draws",
    "Fire",
    "GiveRaise",
    "Interview",
    "MakeOffer",
    "MovePerson",
    "OpenSearch",
    "Promote",
    "ReferenceCheck",
    "Scout",
    "SetLeader",
    "SetPolicy",
    "UpdatePlan",
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
    draws: Draws | None = None,
) -> ActionResult:
    """Apply one action. Raises a domain error, changing nothing, if it is not allowed.

    `draws` makes the generator for any randomness inside the action; by default it is
    stream `actions` keyed by `seq` (player actions).
    """
    if draws is None:
        turn = state.turn

        def draws() -> np.random.Generator:
            return rng.stream(turn, "actions", seq)

    match action:
        case OpenSearch():
            out = open_search(state, action, balance, data, ledger_balances)
        case CloseSearch():
            out = close_search(state, action)
        case Interview():
            out = check_candidate(
                state, action.actor_id, action.candidate_id, "interview", draws, balance, data
            )
        case ReferenceCheck():
            out = check_candidate(
                state,
                action.actor_id,
                action.candidate_id,
                "reference_check",
                draws,
                balance,
                data,
            )
        case MakeOffer():
            out = make_offer(state, action, balance)
        case WithdrawOffer():
            out = withdraw_offer(state, action)
        case Fire():
            out = fire(state, action, balance, data)
        case CreateUnit():
            out = create_unit(state, action, balance)
        case DissolveUnit():
            out = dissolve_unit(state, action, balance)
        case SetLeader():
            out = set_leader(state, action, balance)
        case MovePerson():
            out = move_person(state, action, balance)
        case SetPolicy():
            out = set_policy(state, action, balance)
        case GiveRaise():
            out = give_raise(state, action, balance)
        case Promote():
            out = promote(state, action, balance)
        case CreatePlan():
            out = create_plan(state, action, balance, data)
        case UpdatePlan():
            out = update_plan(state, action, balance, data)
        case ClosePlan():
            out = close_plan(state, action)
        case Scout():
            out = scout(state, action, balance, data)
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
