"""Save-scoped routes for defence and government contracts (M44, docs/formulas.md 57): the
Government screen (tenders by government and area, requirements, the player's bids, awards,
contracts and clearances) and the founder's government actions."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import government_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.government import (
    ClearanceIn,
    GovernmentActionOut,
    GovernmentScreenOut,
    TenderBidIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.government.actions import (
    PlaceBid,
    ProtestAward,
    RequestClearance,
    SponsorFacilityClearance,
    WithdrawBid,
)

router = APIRouter(prefix="/api/saves/{save_id}", tags=["government"])


def _screen(path: Path, data: LoadedData) -> GovernmentScreenOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return government_views.government_out(state, data)


def _act(path: Path, data: LoadedData, action: Action) -> GovernmentActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return GovernmentActionOut(
        government=_screen(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get(
    "/government",
    response_model=GovernmentScreenOut,
    responses=ERRORS,
    operation_id="getGovernment",
)
def get_government(save_id: str, settings: SettingsDep, data: DataDep) -> GovernmentScreenOut:
    """Announced tenders, their requirements, the player's bids, awards and contracts, clearance
    statuses, governments' budgets this year and rivals' published awards."""
    return _screen(_path(settings, save_id), data)


@router.post(
    "/government/tenders/{tender_id}/bid",
    response_model=GovernmentActionOut,
    responses=ERRORS,
    operation_id="placeBid",
)
def place_bid(
    save_id: str, tender_id: int, body: TenderBidIn, settings: SettingsDep, data: DataDep
) -> GovernmentActionOut:
    path = _path(settings, save_id)
    action = PlaceBid(
        _founder_id(_state(path)), tender_id, body.product_id, body.price_cents, tuple(body.team)
    )
    return _act(path, data, action)


@router.post(
    "/government/tenders/{tender_id}/withdraw",
    response_model=GovernmentActionOut,
    responses=ERRORS,
    operation_id="withdrawBid",
)
def withdraw_bid(
    save_id: str, tender_id: int, settings: SettingsDep, data: DataDep
) -> GovernmentActionOut:
    path = _path(settings, save_id)
    return _act(path, data, WithdrawBid(_founder_id(_state(path)), tender_id))


@router.post(
    "/government/tenders/{tender_id}/protest",
    response_model=GovernmentActionOut,
    responses=ERRORS,
    operation_id="protestAward",
)
def protest_award(
    save_id: str, tender_id: int, settings: SettingsDep, data: DataDep
) -> GovernmentActionOut:
    path = _path(settings, save_id)
    return _act(path, data, ProtestAward(_founder_id(_state(path)), tender_id))


@router.post(
    "/government/clearances",
    response_model=GovernmentActionOut,
    responses=ERRORS,
    operation_id="requestClearances",
)
def request_clearances(
    save_id: str, body: ClearanceIn, settings: SettingsDep, data: DataDep
) -> GovernmentActionOut:
    path = _path(settings, save_id)
    action = RequestClearance(_founder_id(_state(path)), tuple(body.person_ids), body.level)
    return _act(path, data, action)


@router.post(
    "/government/facilities/{facility_id}/clearance",
    response_model=GovernmentActionOut,
    responses=ERRORS,
    operation_id="sponsorFacilityClearance",
)
def sponsor_facility_clearance(
    save_id: str, facility_id: int, settings: SettingsDep, data: DataDep
) -> GovernmentActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SponsorFacilityClearance(_founder_id(_state(path)), facility_id))
