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

from tst.sim.actions.authority import (
    AnswerProposal,
    SetAuthority,
    close_proposal,
    pending_proposal,
    proposal_action,
    set_authority,
)
from tst.sim.actions.events import ChooseEvent, choose_event
from tst.sim.actions.facilities import (
    BuildFacility,
    FacilityAction,
    SellCapacity,
    SellFacility,
    SignContract,
    StaffFacility,
    build_facility,
    sell_capacity,
    sell_facility,
    sign_contract,
    staff_facility,
)
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
from tst.sim.actions.hardware import (
    HardwareAction,
    SellPlantCapacity,
    SignManufacturingContract,
    SignWaferContract,
    sell_plant_capacity,
    sign_manufacturing_contract,
    sign_wafer_contract,
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
    acting_company,
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
from tst.sim.actions.public import (
    AppointCeo,
    Buyback,
    DeclareDividend,
    DismissCeo,
    HireBanks,
    OverrideCeo,
    PublicAction,
    SecondaryOffering,
    SetCeoAuthority,
    SetGuidance,
    apply_public,
    mark_overridden,
    override_target,
)
from tst.sim.actions.research import (
    LicenseIn,
    LicenseOut,
    ResearchAction,
    SetProjectBudget,
    StartProject,
    StopProject,
    license_in,
    license_out,
    set_project_budget,
    start_project,
    stop_project,
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
from tst.sim.org import ceo_rules
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

type Action = (
    HiringAction
    | OrgAction
    | ProductAction
    | FinanceAction
    | ChooseEvent
    | ScaleupAction
    | SetAuthority
    | AnswerProposal
    | GeoAction
    | FacilityAction
    | ResearchAction
    | HardwareAction
    | PublicAction
)

ACTION_TYPES: dict[str, type[Any]] = {
    "hire_banks": HireBanks,  # M13
    "set_guidance": SetGuidance,
    "buyback": Buyback,
    "declare_dividend": DeclareDividend,
    "secondary_offering": SecondaryOffering,
    "appoint_ceo": AppointCeo,
    "set_ceo_authority": SetCeoAuthority,
    "dismiss_ceo": DismissCeo,
    "override_ceo": OverrideCeo,
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
    "set_authority": SetAuthority,
    "answer_proposal": AnswerProposal,
    "build_facility": BuildFacility,  # M12a
    "sell_facility": SellFacility,
    "staff_facility": StaffFacility,
    "sign_contract": SignContract,
    "sell_capacity": SellCapacity,
    "sign_manufacturing_contract": SignManufacturingContract,  # M12b
    "sign_wafer_contract": SignWaferContract,
    "sell_plant_capacity": SellPlantCapacity,
    "start_project": StartProject,  # M11
    "stop_project": StopProject,
    "set_project_budget": SetProjectBudget,
    "license_in": LicenseIn,
    "license_out": LicenseOut,
}

__all__ = [
    "ACTION_TYPES",
    "AcceptBridge",
    "AcceptTermSheet",
    "Action",
    "ActionResult",
    "AddSegment",
    "AnswerProposal",
    "AppointCeo",
    "AppointExecutive",
    "AssignUnit",
    "BuildFacility",
    "Buyback",
    "CancelProduct",
    "ChooseEvent",
    "CloseOffice",
    "ClosePlan",
    "CloseSearch",
    "CreatePlan",
    "CreateProduct",
    "CreateUnit",
    "DeclareDividend",
    "DismissCeo",
    "DissolveUnit",
    "Draws",
    "Fire",
    "GiveRaise",
    "HireBanks",
    "Interview",
    "LaunchInRegion",
    "LaunchProduct",
    "LeaseOffice",
    "LicenseIn",
    "LicenseOut",
    "MakeOffer",
    "MovePerson",
    "MoveUnit",
    "NameNominee",
    "OpenSearch",
    "OverrideCeo",
    "Promote",
    "RaiseSafe",
    "ReferenceCheck",
    "RemoveExecutive",
    "RenameUnit",
    "RepayLoan",
    "Scout",
    "ScoutSearch",
    "SecondaryOffering",
    "SellCapacity",
    "SellFacility",
    "SellPlantCapacity",
    "SetAuthority",
    "SetCeoAuthority",
    "SetGuidance",
    "SetLeader",
    "SetMarketing",
    "SetMarketingSplit",
    "SetPolicy",
    "SetPrice",
    "SetProductDivision",
    "SetProjectBudget",
    "SetRegionalPrice",
    "SetSharedServices",
    "SetUnitOffice",
    "SignContract",
    "SignManufacturingContract",
    "SignWaferContract",
    "StaffFacility",
    "StartProject",
    "StartRound",
    "StopProject",
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

    if isinstance(action, AnswerProposal):  # 24.1 (M10c): the proposed action, as the actor
        company = acting_company(state, action.actor_id)
        proposal = pending_proposal(state, company, action.proposal_id)
        if not action.approve:
            return ActionResult(close_proposal(state, proposal, "declined"), (), ())
        inner = apply_action(
            state,
            proposal_action(proposal, action.actor_id),  # type: ignore[arg-type]
            rng,
            balance,
            data,
            ledger_balances,
            seq=seq,
            draws=draws,
        )
        closed = close_proposal(inner.new_state, proposal, "approved")
        return ActionResult(closed, inner.ledger_entries, inner.log_items)
    if isinstance(action, OverrideCeo):  # 25.6 (M13): the decision's undo, as the Chair
        _, undo = override_target(state, action.actor_id, action.decision_id, balance)
        before = state.person_state(action.actor_id).energy
        inner = apply_action(
            state,
            ceo_rules.undo_action(undo, action.actor_id),
            rng,
            balance,
            data,
            ledger_balances,
            seq=seq,
            draws=draws,
        )
        done = mark_overridden(
            inner.new_state, action.decision_id, action.actor_id, before, balance
        )
        return ActionResult(done, inner.ledger_entries, inner.log_items)
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
        case (
            HireBanks()
            | SetGuidance()
            | Buyback()
            | DeclareDividend()
            | SecondaryOffering()
            | AppointCeo()
            | SetCeoAuthority()
            | DismissCeo()
        ):
            out = apply_public(state, action, balance, data, ledger_balances)
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
        case SetAuthority():
            out = set_authority(state, action, balance, data)
        case BuildFacility():  # M12a
            out = build_facility(state, action, balance, data, ledger_balances)
        case SellFacility():
            out = sell_facility(state, action, balance, data)
        case StaffFacility():
            out = staff_facility(state, action, balance)
        case SignContract():
            out = sign_contract(state, action, balance, data)
        case SellCapacity():
            out = sell_capacity(state, action, balance, data)
        case SignManufacturingContract():  # M12b
            out = sign_manufacturing_contract(state, action, balance, data)
        case SignWaferContract():
            out = sign_wafer_contract(state, action, balance, data)
        case SellPlantCapacity():
            out = sell_plant_capacity(state, action, balance, data)
        case StartProject():
            out = start_project(state, action, balance, data)
        case StopProject():
            out = stop_project(state, action, balance)
        case SetProjectBudget():
            out = set_project_budget(state, action, balance)
        case LicenseIn():
            out = license_in(state, action, balance, data, ledger_balances)
        case LicenseOut():
            out = license_out(state, action, balance, data)
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
