"""Save-scoped routes for the founder's own investments (M26, formulas.md 37): the founder
profile's Investments tab, joining rounds, backing a network founder, trading listed shares
and the family office. Actions run through `repository.run_action` with the founder as
actor; personal money only."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import investing_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.investing import (
    BackStartupIn,
    InvestmentsActionOut,
    InvestmentsOut,
    JoinRoundIn,
    MoveIn,
    OfficeMandateIn,
    TradeIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import (
    BackStartup,
    FormFamilyOffice,
    JoinRound,
    MoveFamilyOffice,
    SetOfficeMandate,
    TradeShares,
)
from tst.sim.actions.investing import InvestingAction
from tst.sim.state import GameState

router = APIRouter(prefix="/api/saves/{save_id}", tags=["investing"])


def _out(path: Path, state: GameState, data: LoadedData) -> InvestmentsOut:
    with repository.read_session(path) as session:
        balances = repository.ledger_balances(session)
    return investing_views.investments_out(state, balances, data)


def _act(path: Path, data: LoadedData, action: InvestingAction) -> InvestmentsActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return InvestmentsActionOut(
        investments=_out(path, state, data),
        energy=views.energy(state, data),
        unread_inbox=unread,
    )


@router.get(
    "/founder/investments",
    response_model=InvestmentsOut,
    responses=ERRORS,
    operation_id="getInvestments",
)
def get_investments(save_id: str, settings: SettingsDep, data: DataDep) -> InvestmentsOut:
    """Net worth, angel stakes, open rounds, the network, holdings, trades and the family
    office (37.7)."""
    path = _path(settings, save_id)
    return _out(path, _state(path), data)


@router.post(
    "/founder/angel",
    response_model=InvestmentsActionOut,
    responses=ERRORS,
    operation_id="joinRound",
)
def join_round(
    save_id: str, body: JoinRoundIn, settings: SettingsDep, data: DataDep
) -> InvestmentsActionOut:
    """Put personal cash into a startup's open round (37.2)."""
    path = _path(settings, save_id)
    return _act(path, data, JoinRound(_founder_id(_state(path)), body.company_id, body.cents))


@router.post(
    "/founder/back-startup",
    response_model=InvestmentsActionOut,
    responses=ERRORS,
    operation_id="backStartup",
)
def back_startup(
    save_id: str, body: BackStartupIn, settings: SettingsDep, data: DataDep
) -> InvestmentsActionOut:
    """Back a new startup led by someone from your network (37.2)."""
    path = _path(settings, save_id)
    action = BackStartup(_founder_id(_state(path)), body.founder_id, body.category, body.cents)
    return _act(path, data, action)


@router.post(
    "/founder/shares",
    response_model=InvestmentsActionOut,
    responses=ERRORS,
    operation_id="tradeShares",
)
def trade_shares(
    save_id: str, body: TradeIn, settings: SettingsDep, data: DataDep
) -> InvestmentsActionOut:
    """Buy or sell a listed company's shares with personal cash (37.3)."""
    path = _path(settings, save_id)
    action = TradeShares(_founder_id(_state(path)), body.company_id, body.side, body.shares)
    return _act(path, data, action)


@router.post(
    "/founder/family-office",
    response_model=InvestmentsActionOut,
    responses=ERRORS,
    operation_id="formFamilyOffice",
)
def form_family_office(
    save_id: str, body: OfficeMandateIn, settings: SettingsDep, data: DataDep
) -> InvestmentsActionOut:
    """Form the family office with a mandate (37.4)."""
    path = _path(settings, save_id)
    return _act(path, data, FormFamilyOffice(_founder_id(_state(path)), body.mandate))


@router.post(
    "/founder/family-office/move",
    response_model=InvestmentsActionOut,
    responses=ERRORS,
    operation_id="moveFamilyOffice",
)
def move_family_office(
    save_id: str, body: MoveIn, settings: SettingsDep, data: DataDep
) -> InvestmentsActionOut:
    """Move personal cash into the family office, or out of it (37.4)."""
    path = _path(settings, save_id)
    return _act(path, data, MoveFamilyOffice(_founder_id(_state(path)), body.cents))


@router.post(
    "/founder/family-office/mandate",
    response_model=InvestmentsActionOut,
    responses=ERRORS,
    operation_id="setOfficeMandate",
)
def set_office_mandate(
    save_id: str, body: OfficeMandateIn, settings: SettingsDep, data: DataDep
) -> InvestmentsActionOut:
    """Change the family office's mandate (37.4)."""
    path = _path(settings, save_id)
    return _act(path, data, SetOfficeMandate(_founder_id(_state(path)), body.mandate))
