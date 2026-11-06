"""Save-scoped M&A routes (M14, formulas.md 28): targets, diligence, bids, deals and kept
brands. Actions run through `repository.run_action` with the founder as actor (ADR-0014)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import mna_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.mna import (
    BidIn,
    DealModeIn,
    DiligenceIn,
    DirectiveIn,
    MessageOut,
    MnaActionOut,
    MnaOut,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.mna.antitrust import AcceptRemedy
from tst.sim.mna.deals import AbandonDeal, BidForCompany, SetDealMode, StartDiligence
from tst.sim.mna.integration import SetDirective

router = APIRouter(prefix="/api/saves/{save_id}", tags=["mna"])


def _out(path: Path, data: LoadedData) -> MnaOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        balances = repository.current_balances(session, state.turn)
    return mna_views.mna_out(state, balances, data)


def _act(path: Path, data: LoadedData, action: Action) -> MnaActionOut:
    result = repository.run_action(path, data, action)
    state = result.new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    messages = [
        MessageOut(title=str(p.get("title", "")), detail=str(p.get("detail", "")))
        for p in (dict(i.params) for i in result.log_items if i.template == "deal_update")
    ]
    return MnaActionOut(
        mna=_out(path, data),
        energy=views.energy(state, data),
        unread_inbox=unread,
        messages=messages,
    )


@router.get("/mna", response_model=MnaOut, responses=ERRORS, operation_id="getMna")
def get_mna(save_id: str, settings: SettingsDep, data: DataDep) -> MnaOut:
    """Every company that can be bought (by name), your deals, acquisitions and brands."""
    return _out(_path(settings, save_id), data)


@router.post(
    "/mna/diligence", response_model=MnaActionOut, responses=ERRORS, operation_id="startDiligence"
)
def start_diligence(
    save_id: str, body: DiligenceIn, settings: SettingsDep, data: DataDep
) -> MnaActionOut:
    path = _path(settings, save_id)
    return _act(path, data, StartDiligence(_founder_id(_state(path)), body.company_id))


@router.post("/mna/offers", response_model=MnaActionOut, responses=ERRORS, operation_id="makeBid")
def make_bid(save_id: str, body: BidIn, settings: SettingsDep, data: DataDep) -> MnaActionOut:
    path = _path(settings, save_id)
    action = BidForCompany(
        _founder_id(_state(path)),
        body.company_id,
        body.price_cents,
        body.cash_share,
        body.hostile,
        body.mode,
    )
    return _act(path, data, action)


@router.post(
    "/mna/deals/{deal_id}/mode",
    response_model=MnaActionOut,
    responses=ERRORS,
    operation_id="setDealMode",
)
def set_deal_mode(
    save_id: str, deal_id: int, body: DealModeIn, settings: SettingsDep, data: DataDep
) -> MnaActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SetDealMode(_founder_id(_state(path)), deal_id, body.mode))


@router.post(
    "/mna/deals/{deal_id}/abandon",
    response_model=MnaActionOut,
    responses=ERRORS,
    operation_id="abandonDeal",
)
def abandon_deal(save_id: str, deal_id: int, settings: SettingsDep, data: DataDep) -> MnaActionOut:
    path = _path(settings, save_id)
    return _act(path, data, AbandonDeal(_founder_id(_state(path)), deal_id))


@router.post(
    "/mna/deals/{deal_id}/remedy",
    response_model=MnaActionOut,
    responses=ERRORS,
    operation_id="acceptRemedy",
)
def accept_remedy(save_id: str, deal_id: int, settings: SettingsDep, data: DataDep) -> MnaActionOut:
    path = _path(settings, save_id)
    return _act(path, data, AcceptRemedy(_founder_id(_state(path)), deal_id))


@router.post(
    "/mna/subsidiaries/{company_id}/directive",
    response_model=MnaActionOut,
    responses=ERRORS,
    operation_id="setDirective",
)
def set_directive(
    save_id: str, company_id: int, body: DirectiveIn, settings: SettingsDep, data: DataDep
) -> MnaActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SetDirective(_founder_id(_state(path)), company_id, body.directive))
