"""Save-scoped routes for exploration (M18, formulas.md 34): the Exploration screen and the
founder's exploration actions. Actions run through `repository.run_action` with the founder as
actor."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import exploration_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.exploration import (
    DeskStudyIn,
    DrillIn,
    ExplorationActionOut,
    ExplorationOut,
    LicenceIn,
    StageIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.exploration.pipeline import (
    ExplorationAction,
    OrderDrilling,
    RelinquishProject,
    RenewLicence,
    SellProject,
    StartDeskStudy,
    StartStage,
    TakeLicence,
)

router = APIRouter(prefix="/api/saves/{save_id}", tags=["exploration"])


def _exploration(path: Path, data: LoadedData) -> ExplorationOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        balances = repository.ledger_balances(session)
    return exploration_views.exploration_out(state, balances, data)


def _act(path: Path, data: LoadedData, action: ExplorationAction) -> ExplorationActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return ExplorationActionOut(
        exploration=_exploration(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get(
    "/exploration", response_model=ExplorationOut, responses=ERRORS, operation_id="getExploration"
)
def get_exploration(save_id: str, settings: SettingsDep, data: DataDep) -> ExplorationOut:
    """Regions and their blocks with heat-map bands and licences, desk studies, and every
    project's pipeline, ranges, permit and sale quote (34.5)."""
    return _exploration(_path(settings, save_id), data)


@router.post(
    "/exploration/desk-study",
    response_model=ExplorationActionOut,
    responses=ERRORS,
    operation_id="startDeskStudy",
)
def start_desk_study(
    save_id: str, body: DeskStudyIn, settings: SettingsDep, data: DataDep
) -> ExplorationActionOut:
    """A desk study of one commodity in one region: a heat map of its blocks (34.2)."""
    path = _path(settings, save_id)
    actor = _founder_id(_state(path))
    return _act(path, data, StartDeskStudy(actor, body.region, body.commodity, body.company_id))


@router.post(
    "/exploration/licence",
    response_model=ExplorationActionOut,
    responses=ERRORS,
    operation_id="takeLicence",
)
def take_licence(
    save_id: str, body: LicenceIn, settings: SettingsDep, data: DataDep
) -> ExplorationActionOut:
    """An exploration licence on a free block: a project (34.2)."""
    path = _path(settings, save_id)
    actor = _founder_id(_state(path))
    return _act(path, data, TakeLicence(actor, body.region, body.block, body.company_id))


@router.post(
    "/exploration/projects/{project_id}/renew",
    response_model=ExplorationActionOut,
    responses=ERRORS,
    operation_id="renewLicence",
)
def renew_licence(
    save_id: str, project_id: int, settings: SettingsDep, data: DataDep
) -> ExplorationActionOut:
    path = _path(settings, save_id)
    return _act(path, data, RenewLicence(_founder_id(_state(path)), project_id))


@router.post(
    "/exploration/projects/{project_id}/stage",
    response_model=ExplorationActionOut,
    responses=ERRORS,
    operation_id="startExplorationStage",
)
def start_stage(
    save_id: str, project_id: int, body: StageIn, settings: SettingsDep, data: DataDep
) -> ExplorationActionOut:
    """Start a survey, sampling, a resource estimate, a feasibility study or the permit."""
    path = _path(settings, save_id)
    actor = _founder_id(_state(path))
    return _act(path, data, StartStage(actor, project_id, body.stage, body.commodity))


@router.post(
    "/exploration/projects/{project_id}/drill",
    response_model=ExplorationActionOut,
    responses=ERRORS,
    operation_id="orderDrilling",
)
def order_drilling(
    save_id: str, project_id: int, body: DrillIn, settings: SettingsDep, data: DataDep
) -> ExplorationActionOut:
    """A programme of holes, drilled a few a month and paid hole by hole (34.2)."""
    path = _path(settings, save_id)
    return _act(path, data, OrderDrilling(_founder_id(_state(path)), project_id, body.holes))


@router.post(
    "/exploration/projects/{project_id}/sell",
    response_model=ExplorationActionOut,
    responses=ERRORS,
    operation_id="sellProject",
)
def sell_project(
    save_id: str, project_id: int, settings: SettingsDep, data: DataDep
) -> ExplorationActionOut:
    """Sell the project to a supplier at its quote (34.2)."""
    path = _path(settings, save_id)
    return _act(path, data, SellProject(_founder_id(_state(path)), project_id))


@router.post(
    "/exploration/projects/{project_id}/relinquish",
    response_model=ExplorationActionOut,
    responses=ERRORS,
    operation_id="relinquishProject",
)
def relinquish_project(
    save_id: str, project_id: int, settings: SettingsDep, data: DataDep
) -> ExplorationActionOut:
    path = _path(settings, save_id)
    return _act(path, data, RelinquishProject(_founder_id(_state(path)), project_id))
