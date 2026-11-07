"""Save-scoped routes for the founder's life (M24, formulas.md 32): the founder's profile tabs
(Personal, Foundation, Persona), the Government affairs panel and its lobbying, and the
founder's own actions. Actions run through `repository.run_action` with the founder as actor."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import founder_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.founder import (
    FoundationIn,
    FounderActionOut,
    FounderOut,
    GiftIn,
    LobbyingIn,
    SellSharesIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import (
    CreateFoundation,
    GiveToFoundation,
    SellFounderShares,
    SetLobbying,
)
from tst.sim.actions.founder import FounderAction

router = APIRouter(prefix="/api/saves/{save_id}", tags=["founder"])


def _act(path: Path, data: LoadedData, action: FounderAction) -> FounderActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return FounderActionOut(
        founder=founder_views.founder_out(state, data),
        energy=views.energy(state, data),
        unread_inbox=unread,
    )


@router.get("/founder", response_model=FounderOut, responses=ERRORS, operation_id="getFounder")
def get_founder(save_id: str, settings: SettingsDep, data: DataDep) -> FounderOut:
    """Stress, persona, the personal account, the foundation, influence and legacy (32.8)."""
    return founder_views.founder_out(_state(_path(settings, save_id)), data)


@router.post(
    "/founder/sell-shares",
    response_model=FounderActionOut,
    responses=ERRORS,
    operation_id="sellFounderShares",
)
def sell_shares(
    save_id: str, body: SellSharesIn, settings: SettingsDep, data: DataDep
) -> FounderActionOut:
    """Sell some of your own shares into the float once listed (32.2)."""
    path = _path(settings, save_id)
    return _act(path, data, SellFounderShares(_founder_id(_state(path)), body.shares))


@router.post(
    "/founder/foundation",
    response_model=FounderActionOut,
    responses=ERRORS,
    operation_id="createFoundation",
)
def create_foundation(
    save_id: str, body: FoundationIn, settings: SettingsDep, data: DataDep
) -> FounderActionOut:
    """Create the foundation for a cause (32.3)."""
    path = _path(settings, save_id)
    action = CreateFoundation(_founder_id(_state(path)), body.cause, body.name, body.city)
    return _act(path, data, action)


@router.post(
    "/founder/gifts",
    response_model=FounderActionOut,
    responses=ERRORS,
    operation_id="giveToFoundation",
)
def give(save_id: str, body: GiftIn, settings: SettingsDep, data: DataDep) -> FounderActionOut:
    """Move personal cash to the foundation's endowment (32.3)."""
    path = _path(settings, save_id)
    return _act(path, data, GiveToFoundation(_founder_id(_state(path)), body.amount_cents))


@router.post(
    "/founder/lobbying",
    response_model=FounderActionOut,
    responses=ERRORS,
    operation_id="setLobbying",
)
def set_lobbying(
    save_id: str, body: LobbyingIn, settings: SettingsDep, data: DataDep
) -> FounderActionOut:
    """Set a region's monthly lobbying spend; 0 stops it (32.5)."""
    path = _path(settings, save_id)
    action = SetLobbying(_founder_id(_state(path)), body.region, body.monthly_dollars)
    return _act(path, data, action)
