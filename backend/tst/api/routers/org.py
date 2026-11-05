"""Save-scoped organization routes (M2a): org tree, reorganizations, raises, promotions,
hiring plans, and the morale breakdown.

Actions run through `repository.run_action` with the founder as actor (ADR-0014); previews
apply the action to the loaded state without saving. Responses never carry true values or
unnoticed tags (ADR-0007, formulas.md 13.11).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import guide_views, org_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.org import (
    ChangePreviewOut,
    CreateUnitIn,
    HiringPlanIn,
    HiringPlanOut,
    HiringPlanPatchIn,
    MoraleBreakdownOut,
    MovePersonIn,
    MoveUnitIn,
    OrgActionOut,
    OrgChangeIn,
    OrgOut,
    PayPreviewOut,
    RaiseIn,
    RenameUnitIn,
    SetLeaderIn,
    SetPolicyIn,
    StructureGuideOut,
)
from tst.api.schemas.people import PersonProfileOut
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import (
    Action,
    ClosePlan,
    CreatePlan,
    CreateUnit,
    DissolveUnit,
    GiveRaise,
    MovePerson,
    MoveUnit,
    Promote,
    RenameUnit,
    SetLeader,
    SetPolicy,
    UpdatePlan,
)
from tst.sim.actions.org import live_plan
from tst.sim.errors import InvalidActionError
from tst.sim.hiring.phases import monthly_costs
from tst.sim.state import company_cash

router = APIRouter(prefix="/api/saves/{save_id}", tags=["org"])


def _org_act(path: Path, data: LoadedData, action: Action) -> OrgActionOut:
    result = repository.run_action(path, data, action)
    state = result.new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return OrgActionOut(
        org=org_views.org_out(state, state.player.id, data),
        energy=views.energy(state, data),
        unread_inbox=unread,
    )


# --- Org tree and reorganizations -----------------------------------------------------------


@router.get("/org", response_model=OrgOut, responses=ERRORS, operation_id="getOrg")
def get_org(save_id: str, settings: SettingsDep, data: DataDep) -> OrgOut:
    state = _state(_path(settings, save_id))
    return org_views.org_out(state, state.player.id, data)


@router.get(
    "/org/guide", response_model=StructureGuideOut, responses=ERRORS, operation_id="getOrgGuide"
)
def get_org_guide(save_id: str, settings: SettingsDep, data: DataDep) -> StructureGuideOut:
    """What units, managers, divisions, support and seats do, with live numbers (23.4)."""
    return guide_views.structure_guide(_state(_path(settings, save_id)), data)


@router.post(
    "/org/units",
    response_model=OrgActionOut,
    status_code=201,
    responses=ERRORS,
    operation_id="createUnit",
)
def create_unit(
    save_id: str, body: CreateUnitIn, settings: SettingsDep, data: DataDep
) -> OrgActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    action = CreateUnit(founder, body.kind, body.name, body.parent_id)  # type: ignore[arg-type]
    return _org_act(path, data, action)


@router.post(
    "/org/units/{unit_id}/dissolve",
    response_model=OrgActionOut,
    responses=ERRORS,
    operation_id="dissolveUnit",
)
def dissolve_unit(save_id: str, unit_id: int, settings: SettingsDep, data: DataDep) -> OrgActionOut:
    path = _path(settings, save_id)
    return _org_act(path, data, DissolveUnit(_founder_id(_state(path)), unit_id))


@router.post(
    "/org/units/{unit_id}/rename",
    response_model=OrgActionOut,
    responses=ERRORS,
    operation_id="renameUnit",
)
def rename_unit(
    save_id: str, unit_id: int, body: RenameUnitIn, settings: SettingsDep, data: DataDep
) -> OrgActionOut:
    """Rename a department or team (free)."""
    path = _path(settings, save_id)
    return _org_act(path, data, RenameUnit(_founder_id(_state(path)), unit_id, body.name))


@router.post(
    "/org/units/{unit_id}/move",
    response_model=OrgActionOut,
    responses=ERRORS,
    operation_id="moveUnit",
)
def move_unit(
    save_id: str, unit_id: int, body: MoveUnitIn, settings: SettingsDep, data: DataDep
) -> OrgActionOut:
    """Move a team under a department or the company root (formulas.md 13.1)."""
    path = _path(settings, save_id)
    return _org_act(path, data, MoveUnit(_founder_id(_state(path)), unit_id, body.parent_id))


@router.post(
    "/org/units/{unit_id}/leader",
    response_model=OrgActionOut,
    responses=ERRORS,
    operation_id="setUnitLeader",
)
def set_leader(
    save_id: str, unit_id: int, body: SetLeaderIn, settings: SettingsDep, data: DataDep
) -> OrgActionOut:
    path = _path(settings, save_id)
    return _org_act(path, data, SetLeader(_founder_id(_state(path)), unit_id, body.person_id))


@router.post(
    "/org/people/{person_id}/move",
    response_model=OrgActionOut,
    responses=ERRORS,
    operation_id="movePerson",
)
def move_person(
    save_id: str, person_id: int, body: MovePersonIn, settings: SettingsDep, data: DataDep
) -> OrgActionOut:
    path = _path(settings, save_id)
    return _org_act(path, data, MovePerson(_founder_id(_state(path)), person_id, body.unit_id))


@router.post(
    "/org/policy", response_model=OrgActionOut, responses=ERRORS, operation_id="setUnitPolicy"
)
def set_policy(
    save_id: str, body: SetPolicyIn, settings: SettingsDep, data: DataDep
) -> OrgActionOut:
    path = _path(settings, save_id)
    action = SetPolicy(_founder_id(_state(path)), body.unit_id, body.policy)  # type: ignore[arg-type]
    return _org_act(path, data, action)


def _change_action(founder: int, body: OrgChangeIn) -> Action:
    match body.change:
        case "create_unit":
            return CreateUnit(founder, body.kind or "", body.name or "", body.parent_id)  # type: ignore[arg-type]
        case "dissolve_unit" if body.unit_id is not None:
            return DissolveUnit(founder, body.unit_id)
        case "rename_unit" if body.unit_id is not None:
            return RenameUnit(founder, body.unit_id, body.name or "")
        case "move_unit" if body.unit_id is not None:
            return MoveUnit(founder, body.unit_id, body.parent_id)
        case "set_leader" if body.unit_id is not None:
            return SetLeader(founder, body.unit_id, body.person_id)
        case "move_person" if body.person_id is not None:
            return MovePerson(founder, body.person_id, body.unit_id)
        case "set_policy":
            return SetPolicy(founder, body.unit_id, body.policy)  # type: ignore[arg-type]
    raise InvalidActionError(f"cannot preview change {body.change!r} with these fields")


@router.post(
    "/org/preview",
    response_model=ChangePreviewOut,
    responses=ERRORS,
    operation_id="previewOrgChange",
)
def preview_change(
    save_id: str, body: OrgChangeIn, settings: SettingsDep, data: DataDep
) -> ChangePreviewOut:
    """Energy and one-off morale changes, by person, before a reorganization (13.7)."""
    state = _state(_path(settings, save_id))
    return org_views.change_preview(state, _change_action(_founder_id(state), body), data)


# --- Raises and promotions ------------------------------------------------------------------


def _profile(path: Path, person_id: int, data: LoadedData) -> PersonProfileOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        return views.person_profile(session, state, state.player.id, person_id, data)


@router.post(
    "/people/{person_id}/raise",
    response_model=PersonProfileOut,
    responses=ERRORS,
    operation_id="giveRaise",
)
def give_raise(
    save_id: str, person_id: int, body: RaiseIn, settings: SettingsDep, data: DataDep
) -> PersonProfileOut:
    path = _path(settings, save_id)
    repository.run_action(
        path, data, GiveRaise(_founder_id(_state(path)), person_id, body.salary_cents)
    )
    return _profile(path, person_id, data)


@router.post(
    "/people/{person_id}/raise-preview",
    response_model=PayPreviewOut,
    responses=ERRORS,
    operation_id="previewRaise",
)
def preview_raise(
    save_id: str, person_id: int, body: RaiseIn, settings: SettingsDep, data: DataDep
) -> PayPreviewOut:
    state = _state(_path(settings, save_id))
    action = GiveRaise(_founder_id(state), person_id, body.salary_cents)
    return org_views.pay_preview(state, action, data)


@router.post(
    "/people/{person_id}/promote",
    response_model=PersonProfileOut,
    responses=ERRORS,
    operation_id="promotePerson",
)
def promote(save_id: str, person_id: int, settings: SettingsDep, data: DataDep) -> PersonProfileOut:
    path = _path(settings, save_id)
    repository.run_action(path, data, Promote(_founder_id(_state(path)), person_id))
    return _profile(path, person_id, data)


@router.post(
    "/people/{person_id}/promote-preview",
    response_model=PayPreviewOut,
    responses=ERRORS,
    operation_id="previewPromotion",
)
def preview_promotion(
    save_id: str, person_id: int, settings: SettingsDep, data: DataDep
) -> PayPreviewOut:
    state = _state(_path(settings, save_id))
    return org_views.pay_preview(state, Promote(_founder_id(state), person_id), data)


@router.get(
    "/people/{person_id}/morale",
    response_model=MoraleBreakdownOut,
    responses=ERRORS,
    operation_id="getMoraleBreakdown",
)
def morale_breakdown(
    save_id: str, person_id: int, settings: SettingsDep, data: DataDep
) -> MoraleBreakdownOut:
    path = _path(settings, save_id)
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        cash = company_cash(repository.ledger_balances(session), state.player.id)
    projected = sum(
        amount
        for _, _, amount in monthly_costs(state, state.player.id, data.balance, data.game_data)
    )
    return org_views.morale_breakdown(state, state.player.id, person_id, data, cash, projected)


# --- Hiring plans ---------------------------------------------------------------------------


@router.get(
    "/hiring-plans",
    response_model=list[HiringPlanOut],
    responses=ERRORS,
    operation_id="listHiringPlans",
)
def list_plans(save_id: str, settings: SettingsDep, data: DataDep) -> list[HiringPlanOut]:
    """Plans that are not closed, by id, with what each delegate did last."""
    state = _state(_path(settings, save_id))
    return [org_views.plan_out(state, p, data) for p in state.live_plans(state.player.id)]


@router.post(
    "/hiring-plans",
    response_model=HiringPlanOut,
    status_code=201,
    responses=ERRORS,
    operation_id="createHiringPlan",
)
def create_plan(
    save_id: str, body: HiringPlanIn, settings: SettingsDep, data: DataDep
) -> HiringPlanOut:
    path = _path(settings, save_id)
    action = CreatePlan(
        _founder_id(_state(path)),
        body.owner_id,
        body.role,
        body.target,
        body.channel,  # type: ignore[arg-type]
        body.ratio_bp,
        body.equity_bp,
        body.unit_id,
        body.focus,  # type: ignore[arg-type]
        interest=body.interest,
    )
    result = repository.run_action(path, data, action)
    plan = max(result.new_state.plans, key=lambda p: p.id)
    return org_views.plan_out(result.new_state, plan, data)


@router.patch(
    "/hiring-plans/{plan_id}",
    response_model=HiringPlanOut,
    responses=ERRORS,
    operation_id="updateHiringPlan",
)
def update_plan(
    save_id: str, plan_id: int, body: HiringPlanPatchIn, settings: SettingsDep, data: DataDep
) -> HiringPlanOut:
    path = _path(settings, save_id)
    state = _state(path)
    plan = live_plan(state, state.player.id, plan_id)
    given = body.model_fields_set
    action = UpdatePlan(
        _founder_id(state),
        plan_id,
        owner_id=body.owner_id if body.owner_id is not None else plan.owner_id,
        role=body.role if body.role is not None else plan.role,
        target=body.target if body.target is not None else plan.target,
        channel=body.channel if body.channel is not None else plan.channel,  # type: ignore[arg-type]
        ratio_bp=body.ratio_bp if body.ratio_bp is not None else plan.ratio_bp,
        equity_bp=body.equity_bp if body.equity_bp is not None else plan.equity_bp,
        unit_id=body.unit_id if "unit_id" in given else plan.unit_id,
        focus=body.focus if body.focus is not None else plan.focus,  # type: ignore[arg-type]
    )
    result = repository.run_action(path, data, action)
    updated = result.new_state.plan(plan_id)
    assert updated is not None
    return org_views.plan_out(result.new_state, updated, data)


@router.post(
    "/hiring-plans/{plan_id}/close",
    response_model=HiringPlanOut,
    responses=ERRORS,
    operation_id="closeHiringPlan",
)
def close_plan(save_id: str, plan_id: int, settings: SettingsDep, data: DataDep) -> HiringPlanOut:
    path = _path(settings, save_id)
    result = repository.run_action(path, data, ClosePlan(_founder_id(_state(path)), plan_id))
    closed = result.new_state.plan(plan_id)
    assert closed is not None
    return org_views.plan_out(result.new_state, closed, data)
