"""Save-scoped research routes (M11, formulas.md 21): the Research screen, the era timeline,
projects and licences. Actions run through `repository.run_action` with the founder as actor
(ADR-0014)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import research_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.research import (
    EraOut,
    LicenseIn,
    ProjectBudgetIn,
    ResearchActionOut,
    ResearchOut,
    StartProjectIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.actions.research import (
    LicenseIn as LicenseInAction,
)
from tst.sim.actions.research import (
    LicenseOut,
    SetProjectBudget,
    StartProject,
    StopProject,
)

router = APIRouter(prefix="/api/saves/{save_id}", tags=["research"])


def _act(path: Path, data: LoadedData, action: Action) -> ResearchActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return ResearchActionOut(
        research=research_views.research_out(state, data, state.player.id),
        energy=views.energy(state, data),
        unread_inbox=unread,
    )


@router.get("/research", response_model=ResearchOut, responses=ERRORS, operation_id="getResearch")
def get_research(save_id: str, settings: SettingsDep, data: DataDep) -> ResearchOut:
    """The Research screen: levels, projects, rivals' levels as ranges, licences and eras."""
    state = _state(_path(settings, save_id))
    return research_views.research_out(state, data, state.player.id)  # the UI company (M12r)


@router.get("/eras", response_model=list[EraOut], responses=ERRORS, operation_id="getEras")
def get_eras(save_id: str, settings: SettingsDep, data: DataDep) -> list[EraOut]:
    """The era timeline (the Market screen shows it too, 21.4)."""
    state = _state(_path(settings, save_id))
    return research_views.eras_out(state, data, state.player.id)


@router.post(
    "/research/projects",
    response_model=ResearchActionOut,
    responses=ERRORS,
    operation_id="startProject",
)
def start_project(
    save_id: str, body: StartProjectIn, settings: SettingsDep, data: DataDep
) -> ResearchActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, StartProject(founder, body.unit_id, body.domain, body.budget_cents))


@router.post(
    "/research/projects/{project_id}/stop",
    response_model=ResearchActionOut,
    responses=ERRORS,
    operation_id="stopProject",
)
def stop_project(
    save_id: str, project_id: int, settings: SettingsDep, data: DataDep
) -> ResearchActionOut:
    path = _path(settings, save_id)
    return _act(path, data, StopProject(_founder_id(_state(path)), project_id))


@router.post(
    "/research/projects/{project_id}/budget",
    response_model=ResearchActionOut,
    responses=ERRORS,
    operation_id="setProjectBudget",
)
def set_project_budget(
    save_id: str, project_id: int, body: ProjectBudgetIn, settings: SettingsDep, data: DataDep
) -> ResearchActionOut:
    path = _path(settings, save_id)
    action = SetProjectBudget(_founder_id(_state(path)), project_id, body.budget_cents)
    return _act(path, data, action)


@router.post(
    "/research/licenses/in",
    response_model=ResearchActionOut,
    responses=ERRORS,
    operation_id="licenseIn",
)
def license_in(
    save_id: str, body: LicenseIn, settings: SettingsDep, data: DataDep
) -> ResearchActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, LicenseInAction(founder, body.company_id, body.domain, body.points))


@router.post(
    "/research/licenses/out",
    response_model=ResearchActionOut,
    responses=ERRORS,
    operation_id="licenseOut",
)
def license_out(
    save_id: str, body: LicenseIn, settings: SettingsDep, data: DataDep
) -> ResearchActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, LicenseOut(founder, body.company_id, body.domain, body.points))
