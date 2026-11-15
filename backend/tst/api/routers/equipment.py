"""Save-scoped routes for semiconductor equipment (M33, docs/formulas.md 47): the Equipment
screen and the founder's tool orders, prepayments and lithography programme. Actions run
through `repository.run_action` with the founder as actor."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import equipment_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.equipment import (
    EquipmentActionOut,
    EquipmentOut,
    LithoStageIn,
    LithoStartIn,
    OrderToolsIn,
    PrepayIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.equipment.actions import (
    OrderTools,
    PrepayOrder,
    SetLithoFunding,
    StartLitho,
    StopLitho,
)

router = APIRouter(prefix="/api/saves/{save_id}", tags=["equipment"])


def _equipment(path: Path, data: LoadedData) -> EquipmentOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return equipment_views.equipment_out(state, data)


def _act(path: Path, data: LoadedData, action: Action) -> EquipmentActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return EquipmentActionOut(
        equipment=_equipment(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get(
    "/equipment", response_model=EquipmentOut, responses=ERRORS, operation_id="getEquipment"
)
def get_equipment(save_id: str, settings: SettingsDep, data: DataDep) -> EquipmentOut:
    """Tool generations, prices, the player's orders and queue place as a range, stock,
    controls and the lithography programme (47.6)."""
    return _equipment(_path(settings, save_id), data)


@router.post(
    "/equipment/orders",
    response_model=EquipmentActionOut,
    responses=ERRORS,
    operation_id="orderTools",
)
def order_tools(
    save_id: str, body: OrderToolsIn, settings: SettingsDep, data: DataDep
) -> EquipmentActionOut:
    path = _path(settings, save_id)
    action = OrderTools(_founder_id(_state(path)), body.generation, body.tools, body.prepay)
    return _act(path, data, action)


@router.post(
    "/equipment/prepay",
    response_model=EquipmentActionOut,
    responses=ERRORS,
    operation_id="prepayToolOrder",
)
def prepay(
    save_id: str, body: PrepayIn, settings: SettingsDep, data: DataDep
) -> EquipmentActionOut:
    path = _path(settings, save_id)
    return _act(path, data, PrepayOrder(_founder_id(_state(path)), body.order_id))


@router.post(
    "/equipment/litho/start",
    response_model=EquipmentActionOut,
    responses=ERRORS,
    operation_id="startLitho",
)
def start_litho(
    save_id: str, body: LithoStartIn, settings: SettingsDep, data: DataDep
) -> EquipmentActionOut:
    path = _path(settings, save_id)
    return _act(path, data, StartLitho(_founder_id(_state(path)), body.stage, body.funding))


@router.post(
    "/equipment/litho/funding",
    response_model=EquipmentActionOut,
    responses=ERRORS,
    operation_id="setLithoFunding",
)
def set_funding(
    save_id: str, body: LithoStartIn, settings: SettingsDep, data: DataDep
) -> EquipmentActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SetLithoFunding(_founder_id(_state(path)), body.stage, body.funding))


@router.post(
    "/equipment/litho/stop",
    response_model=EquipmentActionOut,
    responses=ERRORS,
    operation_id="stopLitho",
)
def stop_litho(
    save_id: str, body: LithoStageIn, settings: SettingsDep, data: DataDep
) -> EquipmentActionOut:
    path = _path(settings, save_id)
    return _act(path, data, StopLitho(_founder_id(_state(path)), body.stage))
