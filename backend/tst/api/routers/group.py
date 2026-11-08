"""Save-scoped routes for the group (M16, formulas.md 31): the Group screen and the founder's
actions as Chair. Actions run through `repository.run_action` with the founder as actor."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import group_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.group import GroupActionOut, GroupOut
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.group.actions import FormHolding, GroupAction

router = APIRouter(prefix="/api/saves/{save_id}", tags=["group"])


def _group(path: Path, data: LoadedData) -> GroupOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        balances = repository.ledger_balances(session)
    return group_views.group_out(state, balances, data)


def _act(path: Path, data: LoadedData, action: GroupAction) -> GroupActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return GroupActionOut(
        group=_group(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get("/group", response_model=GroupOut, responses=ERRORS, operation_id="getGroup")
def get_group(save_id: str, settings: SettingsDep, data: DataDep) -> GroupOut:
    """The entity tree with stakes, treatments and each company's numbers; the holding
    company's gate before it is formed (31.2, 31.10)."""
    return _group(_path(settings, save_id), data)


@router.post(
    "/group/form", response_model=GroupActionOut, responses=ERRORS, operation_id="formHolding"
)
def form_holding(save_id: str, settings: SettingsDep, data: DataDep) -> GroupActionOut:
    """Form the holding company: it takes the listing, the cap table and the board; the
    company and its brands become its subsidiaries (31.2)."""
    path = _path(settings, save_id)
    return _act(path, data, FormHolding(_founder_id(_state(path))))
