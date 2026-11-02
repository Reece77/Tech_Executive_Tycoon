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

from tst.sim.actions.events import ChooseEvent, choose_event
from tst.sim.actions.finance import (
    AcceptBridge,
    AcceptTermSheet,
    FinanceAction,
    NameNominee,
    RaiseSafe,
    RepayLoan,
    StartRound,
    TakeLoan,
    apply_finance,
)
from tst.sim.actions.geo import (
    CloseOffice,
    GeoAction,
    LaunchInRegion,
    LeaseOffice,
    SetMarketingSplit,
    SetRegionalPrice,
    SetUnitOffice,
    close_office,
    launch_in_region,
    lease_office,
    set_marketing_split,
    set_regional_price,
    set_unit_office,
)
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
    MoveUnit,
    OrgAction,
    Promote,
    RenameUnit,
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
    move_unit,
    promote,
    rename_unit,
    scout,
    set_leader,
    set_policy,
    update_plan,
)
from tst.sim.actions.products import (
    AddSegment,
    AssignUnit,
    CancelProduct,
    CreateProduct,
    LaunchProduct,
    ProductAction,
    ScoutSearch,
    SetMarketing,
    SetPrice,
    SunsetProduct,
    UnassignUnit,
    add_segment,
    assign_unit,
    cancel_product,
    create_product,
    launch_product,
    scout_search,
    set_marketing,
    set_price,
    sunset_product,
    unassign_unit,
)
from tst.sim.actions.scaleup import (
    AppointExecutive,
    RemoveExecutive,
    ScaleupAction,
    SetProductDivision,
    SetSharedServices,
    appoint_executive,
    remove_executive,
    set_product_division,
    set_shared_services,
)
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import GameOverError, InvalidActionError
from tst.sim.geo.cities import settle_home_cities
from tst.sim.ledger import LedgerBalances, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

type Action = (
    HiringAction
    | OrgAction
    | ProductAction
    | FinanceAction
    | ChooseEvent
    | ScaleupAction
    | GeoAction
)

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
    "move_unit": MoveUnit,
    "rename_unit": RenameUnit,
    "set_leader": SetLeader,
    "move_person": MovePerson,
    "set_policy": SetPolicy,
    "give_raise": GiveRaise,
    "promote": Promote,
    "create_plan": CreatePlan,
    "update_plan": UpdatePlan,
    "close_plan": ClosePlan,
    "scout": Scout,
    "create_product": CreateProduct,
    "set_price": SetPrice,
    "add_segment": AddSegment,
    "assign_unit": AssignUnit,
    "unassign_unit": UnassignUnit,
    "set_marketing": SetMarketing,
    "launch_product": LaunchProduct,
    "sunset_product": SunsetProduct,
    "cancel_product": CancelProduct,
    "scout_search": ScoutSearch,
    "raise_safe": RaiseSafe,
    "start_round": StartRound,
    "accept_term_sheet": AcceptTermSheet,
    "accept_bridge": AcceptBridge,
    "name_nominee": NameNominee,
    "take_loan": TakeLoan,  # M10
    "repay_loan": RepayLoan,
    "choose_event": ChooseEvent,
    "set_product_division": SetProductDivision,  # M8
    "set_shared_services": SetSharedServices,
    "appoint_executive": AppointExecutive,
    "remove_executive": RemoveExecutive,
    "lease_office": LeaseOffice,  # M9
    "close_office": CloseOffice,
    "set_unit_office": SetUnitOffice,
    "launch_in_region": LaunchInRegion,
    "set_regional_price": SetRegionalPrice,
    "set_marketing_split": SetMarketingSplit,
}

__all__ = [
    "ACTION_TYPES",
    "AcceptBridge",
    "AcceptTermSheet",
    "Action",
    "ActionResult",
    "AddSegment",
    "AppointExecutive",
    "AssignUnit",
    "CancelProduct",
    "ChooseEvent",
    "CloseOffice",
    "ClosePlan",
    "CloseSearch",
    "CreatePlan",
    "CreateProduct",
    "CreateUnit",
    "DissolveUnit",
    "Draws",
    "Fire",
    "GiveRaise",
    "Interview",
    "LaunchInRegion",
    "LaunchProduct",
    "LeaseOffice",
    "MakeOffer",
    "MovePerson",
    "MoveUnit",
    "NameNominee",
    "OpenSearch",
    "Promote",
    "RaiseSafe",
    "ReferenceCheck",
    "RemoveExecutive",
    "RenameUnit",
    "RepayLoan",
    "Scout",
    "ScoutSearch",
    "SetLeader",
    "SetMarketing",
    "SetMarketingSplit",
    "SetPolicy",
    "SetPrice",
    "SetProductDivision",
    "SetRegionalPrice",
    "SetSharedServices",
    "SetUnitOffice",
    "StartRound",
    "SunsetProduct",
    "TakeLoan",
    "UnassignUnit",
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
    if state.ended:
        raise GameOverError(f"the game is over ({state.save_meta.game_state.replace('_', ' ')})")
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
        case MoveUnit():
            out = move_unit(state, action, balance)
        case RenameUnit():
            out = rename_unit(state, action)
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
        case CreateProduct():
            out = create_product(state, action, balance, data)
        case SetPrice():
            out = set_price(state, action, balance)
        case AddSegment():
            out = add_segment(state, action, balance, data)
        case AssignUnit():
            out = assign_unit(state, action, balance)
        case UnassignUnit():
            out = unassign_unit(state, action, balance)
        case SetMarketing():
            out = set_marketing(state, action, balance)
        case LaunchProduct():
            out = launch_product(state, action, balance, data)
        case SunsetProduct():
            out = sunset_product(state, action, balance)
        case CancelProduct():
            out = cancel_product(state, action, balance)
        case ScoutSearch():
            out = scout_search(state, action, balance, data)
        case (
            RaiseSafe()
            | StartRound()
            | AcceptTermSheet()
            | AcceptBridge()
            | NameNominee()
            | TakeLoan()
            | RepayLoan()
        ):
            out = apply_finance(state, action, balance, data, ledger_balances)
        case ChooseEvent():
            out = choose_event(state, action, balance, data)
        case SetProductDivision():
            out = set_product_division(state, action, balance)
        case SetSharedServices():
            out = set_shared_services(state, action, balance)
        case AppointExecutive():
            out = appoint_executive(state, action, balance, data)
        case RemoveExecutive():
            out = remove_executive(state, action, balance)
        case LeaseOffice():
            out = lease_office(state, action, balance, data, ledger_balances)
        case CloseOffice():
            out = close_office(state, action, balance, data)
        case SetUnitOffice():
            out = set_unit_office(state, action, balance, data)
        case LaunchInRegion():
            out = launch_in_region(state, action, balance, data, ledger_balances)
        case SetRegionalPrice():
            out = set_regional_price(state, action, balance, data)
        case SetMarketingSplit():
            out = set_marketing_split(state, action, balance, data)
    new_state = out.state
    actor = new_state.employment_of(action.actor_id) or state.employment_of(action.actor_id)
    if actor is not None:  # people live where they work (M9, 19.2)
        new_state = settle_home_cities(new_state, actor.company_id, balance, data)
    return ActionResult(new_state=new_state, ledger_entries=out.entries, log_items=out.log)


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
