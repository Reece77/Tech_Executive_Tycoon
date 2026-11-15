"""Save-scoped routes for regulation (M34, docs/formulas.md 48): the Regulation screen, and the
founder's actions on it (putting right every setting a duty forbids; meeting a structural order
by sale or spin-off). Actions run through `repository.run_action` with the founder as actor."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import regulation_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.regulation import AnswerOrderIn, RegulationActionOut, RegulationOut
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.regulation.actions import AnswerOrder, ComplyDuties

router = APIRouter(prefix="/api/saves/{save_id}", tags=["regulation"])


def _regulation(path: Path, data: LoadedData) -> RegulationOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        balances = repository.ledger_balances(session)
    return regulation_views.regulation_out(state, data, balances)


def _act(path: Path, data: LoadedData, action: Action) -> RegulationActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return RegulationActionOut(
        regulation=_regulation(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get(
    "/regulation", response_model=RegulationOut, responses=ERRORS, operation_id="getRegulation"
)
def get_regulation(save_id: str, settings: SettingsDep, data: DataDep) -> RegulationOut:
    """Regulators by region, designations and thresholds, duties, investigations with their
    stages, fines, warning signs and orders (48.6)."""
    return _regulation(_path(settings, save_id), data)


@router.post(
    "/regulation/comply",
    response_model=RegulationActionOut,
    responses=ERRORS,
    operation_id="complyDuties",
)
def comply_duties(save_id: str, settings: SettingsDep, data: DataDep) -> RegulationActionOut:
    path = _path(settings, save_id)
    return _act(path, data, ComplyDuties(_founder_id(_state(path))))


@router.post(
    "/regulation/orders/answer",
    response_model=RegulationActionOut,
    responses=ERRORS,
    operation_id="answerOrder",
)
def answer_order(
    save_id: str, body: AnswerOrderIn, settings: SettingsDep, data: DataDep
) -> RegulationActionOut:
    path = _path(settings, save_id)
    return _act(path, data, AnswerOrder(_founder_id(_state(path)), body.order_id, body.how))
