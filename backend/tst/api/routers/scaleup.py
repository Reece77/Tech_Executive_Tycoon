"""Save-scoped scale-up routes (M8, formulas.md 18): divisions and shared services, products'
divisions, executive seats, and division statements.

Actions run through `repository.run_action` with the founder as actor (ADR-0014). Seat fit
and effects are estimates from displayed ranges, never true s or e (18.8).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from tst.api import scaleup_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.scaleup import (
    AppointIn,
    DivisionStatementsOut,
    ProductDivisionIn,
    ScaleupActionOut,
    ScaleupOut,
    SeatCandidatesOut,
    SharedServicesIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import (
    Action,
    AppointExecutive,
    RemoveExecutive,
    SetProductDivision,
    SetSharedServices,
)
from tst.sim.errors import InvalidActionError
from tst.sim.org.models import SEATS
from tst.sim.state import GameState

router = APIRouter(prefix="/api/saves/{save_id}", tags=["scaleup"])


def _scaleup(path: Path, state: GameState, data: LoadedData) -> ScaleupOut:
    with repository.read_session(path) as session:
        lines = repository.division_lines(session, state.player.id)
        months = repository.division_months(session, state.player.id)
    profit = scaleup_views.last_month_profit(lines, months, state, data)
    return scaleup_views.scaleup_out(state, data, profit)


def _act(path: Path, data: LoadedData, action: Action) -> ScaleupActionOut:
    result = repository.run_action(path, data, action)
    state = result.new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return ScaleupActionOut(
        scaleup=_scaleup(path, state, data),
        energy=views.energy(state, data),
        unread_inbox=unread,
    )


def _seat(seat: str) -> str:
    if seat not in SEATS:
        raise InvalidActionError(f"unknown executive seat {seat!r}")
    return seat


@router.get("/scaleup", response_model=ScaleupOut, responses=ERRORS, operation_id="getScaleup")
def get_scaleup(save_id: str, settings: SettingsDep, data: DataDep) -> ScaleupOut:
    """Divisions, support coverage, cross-division products and the executive team."""
    path = _path(settings, save_id)
    return _scaleup(path, _state(path), data)


@router.post(
    "/scaleup/divisions/{unit_id}/services",
    response_model=ScaleupActionOut,
    responses=ERRORS,
    operation_id="setSharedServices",
)
def set_shared_services(
    save_id: str, unit_id: int, body: SharedServicesIn, settings: SettingsDep, data: DataDep
) -> ScaleupActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    action = SetSharedServices(founder, unit_id, body.services)  # type: ignore[arg-type]
    return _act(path, data, action)


@router.post(
    "/scaleup/products/{product_id}/division",
    response_model=ScaleupActionOut,
    responses=ERRORS,
    operation_id="setProductDivision",
)
def set_product_division(
    save_id: str, product_id: int, body: ProductDivisionIn, settings: SettingsDep, data: DataDep
) -> ScaleupActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, SetProductDivision(founder, product_id, body.division_id))


@router.get(
    "/scaleup/seats/{seat}/candidates",
    response_model=SeatCandidatesOut,
    responses=ERRORS,
    operation_id="getSeatCandidates",
)
def seat_candidates(
    save_id: str, seat: str, settings: SettingsDep, data: DataDep
) -> SeatCandidatesOut:
    """Staff with their fit and estimated effect for one seat (the Appoint dialog)."""
    state = _state(_path(settings, save_id))
    return scaleup_views.seat_candidates_out(state, _seat(seat), data)


@router.post(
    "/scaleup/seats/{seat}/appoint",
    response_model=ScaleupActionOut,
    responses=ERRORS,
    operation_id="appointExecutive",
)
def appoint(
    save_id: str, seat: str, body: AppointIn, settings: SettingsDep, data: DataDep
) -> ScaleupActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, AppointExecutive(founder, _seat(seat), body.person_id))


@router.post(
    "/scaleup/seats/{seat}/remove",
    response_model=ScaleupActionOut,
    responses=ERRORS,
    operation_id="removeExecutive",
)
def remove(save_id: str, seat: str, settings: SettingsDep, data: DataDep) -> ScaleupActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, RemoveExecutive(founder, _seat(seat)))


@router.get(
    "/finance/divisions",
    response_model=DivisionStatementsOut,
    responses=ERRORS,
    operation_id="getDivisionStatements",
)
def get_division_statements(
    save_id: str,
    settings: SettingsDep,
    data: DataDep,
    period: Annotated[Literal["month", "quarter", "year"], Query()] = "month",
) -> DivisionStatementsOut:
    """Each division's statement with its shared-services allocation (18.1); newest first."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        lines = repository.division_lines(session, state.player.id)
        months = repository.division_months(session, state.player.id)
    return scaleup_views.division_statements_out(state, lines, months, period, data)
