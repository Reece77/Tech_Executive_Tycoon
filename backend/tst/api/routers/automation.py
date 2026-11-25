"""Save-scoped automation routes (M27a, formulas.md 40): the Automation screen, giving and
taking back areas, their settings, Automate everything (a plan, then the confirmed plan), the
month's digest and an owner's record. Actions run through `repository.run_action` with the
founder as actor (ADR-0014); Automate everything is one action per area, in order."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from tst.api import automation_views, interruptions, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.automation import (
    AreaIn,
    AreaOwnerIn,
    AreaSettingsIn,
    AutomateAllIn,
    AutomatePlanOut,
    AutomationActionOut,
    AutomationOut,
    DigestOut,
    HeadcountTargetIn,
    RecordOut,
)
from tst.config import Settings
from tst.db import inbox, repository
from tst.db.models import InboxItemRow
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.automation.actions import (
    SetAreaOwner,
    SetAreaSettings,
    SetHeadcountTarget,
    TakeBackArea,
)
from tst.sim.calendar import HISTORY_START_TURN
from tst.sim.errors import InvalidActionError
from tst.sim.state import GameState, company_cash

router = APIRouter(prefix="/api/saves/{save_id}", tags=["automation"])


def _cash(path: Path, state: GameState, company_id: int | None = None) -> int:
    company = state.player.id if company_id is None else company_id
    with repository.read_session(path) as session:
        return company_cash(repository.current_balances(session, state.turn), company)


def _out(
    path: Path,
    state: GameState,
    data: LoadedData,
    settings: Settings,
    company_id: int | None = None,
) -> AutomationOut:
    stop = interruptions.stop_for_approvals(settings.resolved_save_dir())
    cash = _cash(path, state, company_id)
    return automation_views.automation_out(state, cash, data, stop, company_id)


def _act(
    path: Path,
    data: LoadedData,
    settings: Settings,
    actions: list[Action],
    company_id: int | None = None,
) -> AutomationActionOut:
    state = _state(path)
    for action in actions:
        state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return AutomationActionOut(
        automation=_out(path, state, data, settings, company_id),
        energy=views.energy(state, data),
        unread_inbox=unread,
    )


@router.get(
    "/automation", response_model=AutomationOut, responses=ERRORS, operation_id="getAutomation"
)
def get_automation(
    save_id: str,
    settings: SettingsDep,
    data: DataDep,
    company_id: Annotated[int | None, Query(description="M27b: a subsidiary")] = None,
) -> AutomationOut:
    """Every area: who runs it (or why nobody can yet), the people who could, limits,
    priority, this month's decisions and proposals waiting (40.8); for the player's company or
    (M27b) one of its group's subsidiaries."""
    path = _path(settings, save_id)
    return _out(path, _state(path), data, settings, company_id)


@router.post(
    "/automation/owner",
    response_model=AutomationActionOut,
    responses=ERRORS,
    operation_id="setAreaOwner",
)
def set_area_owner(
    save_id: str, body: AreaOwnerIn, settings: SettingsDep, data: DataDep
) -> AutomationActionOut:
    """Give an area to a person (energy automation.change_energy)."""
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    action = SetAreaOwner(
        founder, body.area, body.person_id, body.limit_cents, body.priority, body.company_id
    )
    return _act(path, data, settings, [action], body.company_id)


@router.post(
    "/automation/take-back",
    response_model=AutomationActionOut,
    responses=ERRORS,
    operation_id="takeBackArea",
)
def take_back_area(
    save_id: str, body: AreaIn, settings: SettingsDep, data: DataDep
) -> AutomationActionOut:
    """Manage an area yourself again."""
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    action = TakeBackArea(founder, body.area, body.company_id)
    return _act(path, data, settings, [action], body.company_id)


@router.post(
    "/automation/settings",
    response_model=AutomationActionOut,
    responses=ERRORS,
    operation_id="setAreaSettings",
)
def set_area_settings(
    save_id: str, body: AreaSettingsIn, settings: SettingsDep, data: DataDep
) -> AutomationActionOut:
    """An owned area's limit, priority, routine events and bold claims. Free."""
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    rails = (
        None
        if body.guardrails is None
        else tuple(sorted((g.key, g.value) for g in body.guardrails))
    )
    action = SetAreaSettings(
        founder,
        body.area,
        body.limit_cents,
        body.priority,
        body.answer_events,
        body.allow_bold,
        body.company_id,
        body.budget_cents,
        rails,
    )
    return _act(path, data, settings, [action], body.company_id)


@router.post(
    "/automation/headcount",
    response_model=AutomationActionOut,
    responses=ERRORS,
    operation_id="setHeadcountTarget",
)
def set_headcount_target(
    save_id: str, body: HeadcountTargetIn, settings: SettingsDep, data: DataDep
) -> AutomationActionOut:
    """M27b: a unit's headcount target in a role (0 removes it), which Hiring fills. Free."""
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    action = SetHeadcountTarget(founder, body.unit_id, body.role, body.target, body.company_id)
    return _act(path, data, settings, [action], body.company_id)


@router.get(
    "/automation/plan",
    response_model=AutomatePlanOut,
    responses=ERRORS,
    operation_id="getAutomatePlan",
)
def get_plan(
    save_id: str,
    settings: SettingsDep,
    data: DataDep,
    company_id: Annotated[int | None, Query(description="M27b: a subsidiary")] = None,
) -> AutomatePlanOut:
    """Automate everything, before anything changes: who would run each area (40.8); inside a
    subsidiary its CEO first."""
    path = _path(settings, save_id)
    state = _state(path)
    return automation_views.plan_out(state, _cash(path, state, company_id), data, company_id)


@router.post(
    "/automation/all",
    response_model=AutomationActionOut,
    responses=ERRORS,
    operation_id="automateEverything",
)
def automate_all(
    save_id: str, body: AutomateAllIn, settings: SettingsDep, data: DataDep
) -> AutomationActionOut:
    """Apply the confirmed plan, area by area."""
    if not body.assignments:
        raise InvalidActionError("nothing to automate")
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    actions: list[Action] = [
        SetAreaOwner(founder, a.area, a.person_id, a.limit_cents, a.priority, a.company_id)
        for a in body.assignments
    ]
    return _act(path, data, settings, actions, body.assignments[0].company_id)


@router.get(
    "/automation/digest",
    response_model=DigestOut | None,
    responses=ERRORS,
    operation_id="getDigest",
)
def get_digest(
    save_id: str,
    settings: SettingsDep,
    data: DataDep,
    turn: Annotated[int | None, Query(ge=HISTORY_START_TURN)] = None,  # M50: from 2008
) -> DigestOut | None:
    """A month's digest (40.4): the last month played unless `turn` names one; null when no
    area was automated that month."""
    path = _path(settings, save_id)
    state = _state(path)
    month = state.turn - 1 if turn is None else turn
    with repository.read_session(path) as session:
        rows = session.scalars(
            select(InboxItemRow).where(
                InboxItemRow.company_id == state.player.id, InboxItemRow.turn == month
            )
        ).all()
        item = next((r.id for r in rows if r.template == "digest"), None)
        items = [r.id for r in rows if r.in_digest]
    return automation_views.digest_out(state, month, data, item, items)


@router.get(
    "/automation/record/{person_id}",
    response_model=RecordOut,
    responses=ERRORS,
    operation_id="getOwnerRecord",
)
def get_record(save_id: str, person_id: int, settings: SettingsDep, data: DataDep) -> RecordOut:
    """An owner's record (40.3): decisions, proposals and their outcomes, pitches."""
    path = _path(settings, save_id)
    state = _state(path)
    if not any(p.id == person_id for p in state.people):
        raise InvalidActionError(f"no person {person_id}")
    return automation_views.record_out(state, person_id, data)
