"""Save-scoped routes for mines (M19, formulas.md 35): the Mines screen and the founder's mining
actions. Actions run through `repository.run_action` with the founder as actor."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import mining_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.mining import (
    BidAnswerIn,
    BuildMineIn,
    CareIn,
    FoundSubsidiaryIn,
    MinesActionOut,
    MineSafetyIn,
    MineSaleDealIn,
    MineSalesIn,
    MinesOut,
    MineStaffIn,
    TransferIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.mining.actions import (
    AnswerRivalBid,
    BuildMine,
    CareMaintenance,
    CloseMine,
    FoundSubsidiary,
    MiningAction,
    SetMineSafety,
    SetMineSales,
    SignMineSale,
    StaffMine,
    TransferAsset,
)

router = APIRouter(prefix="/api/saves/{save_id}", tags=["mining"])


def _mines(path: Path, data: LoadedData) -> MinesOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        balances = repository.ledger_balances(session)
    return mining_views.mines_out(state, balances, data)


def _act(path: Path, data: LoadedData, action: MiningAction) -> MinesActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return MinesActionOut(
        mines=_mines(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


def _actor(path: Path) -> int:
    return _founder_id(_state(path))


@router.get("/mines", response_model=MinesOut, responses=ERRORS, operation_id="getMines")
def get_mines(save_id: str, settings: SettingsDep, data: DataDep) -> MinesOut:
    """The group's mines (construction, output, grade, cost against price, reserves as ranges,
    staff, events, closure), permitted projects to build on, assets to move, rivals' bids,
    resource-nationalism events and rival miners (35)."""
    return _mines(_path(settings, save_id), data)


@router.post(
    "/mines/subsidiaries",
    response_model=MinesActionOut,
    responses=ERRORS,
    operation_id="foundSubsidiary",
)
def found_subsidiary(
    save_id: str, body: FoundSubsidiaryIn, settings: SettingsDep, data: DataDep
) -> MinesActionOut:
    """35.1: a new, wholly owned subsidiary with a cash injection from the group."""
    path = _path(settings, save_id)
    return _act(path, data, FoundSubsidiary(_actor(path), body.name, body.region, body.cents))


@router.post(
    "/mines/transfer", response_model=MinesActionOut, responses=ERRORS, operation_id="transferAsset"
)
def transfer_asset(
    save_id: str, body: TransferIn, settings: SettingsDep, data: DataDep
) -> MinesActionOut:
    """35.1: move a project or a facility to another group company at book value."""
    path = _path(settings, save_id)
    return _act(
        path,
        data,
        TransferAsset(_actor(path), body.to_company_id, body.project_id, body.facility_id),
    )


@router.post(
    "/mines/build", response_model=MinesActionOut, responses=ERRORS, operation_id="buildMine"
)
def build_mine(
    save_id: str, body: BuildMineIn, settings: SettingsDep, data: DataDep
) -> MinesActionOut:
    """35.2: build a mine on a permitted project."""
    path = _path(settings, save_id)
    return _act(path, data, BuildMine(_actor(path), body.project_id, body.capacity_t))


@router.post(
    "/mines/{mine_id}/sales",
    response_model=MinesActionOut,
    responses=ERRORS,
    operation_id="setMineSales",
)
def set_mine_sales(
    save_id: str, mine_id: int, body: MineSalesIn, settings: SettingsDep, data: DataDep
) -> MinesActionOut:
    """35.3: spot, or a group company at a transfer price."""
    path = _path(settings, save_id)
    return _act(
        path, data, SetMineSales(_actor(path), mine_id, body.buyer_id, body.price_kind, body.margin)
    )


@router.post(
    "/mines/{mine_id}/staff",
    response_model=MinesActionOut,
    responses=ERRORS,
    operation_id="staffMine",
)
def staff_mine(
    save_id: str, mine_id: int, body: MineStaffIn, settings: SettingsDep, data: DataDep
) -> MinesActionOut:
    path = _path(settings, save_id)
    return _act(path, data, StaffMine(_actor(path), mine_id, body.unit_id))


@router.post(
    "/mines/{mine_id}/safety",
    response_model=MinesActionOut,
    responses=ERRORS,
    operation_id="setMineSafety",
)
def set_mine_safety(
    save_id: str, mine_id: int, body: MineSafetyIn, settings: SettingsDep, data: DataDep
) -> MinesActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SetMineSafety(_actor(path), mine_id, body.safety))


@router.post(
    "/mines/{mine_id}/deals",
    response_model=MinesActionOut,
    responses=ERRORS,
    operation_id="signMineSale",
)
def sign_mine_sale(
    save_id: str, mine_id: int, body: MineSaleDealIn, settings: SettingsDep, data: DataDep
) -> MinesActionOut:
    """35.3: a fixed-price contract or an offtake, the mine as seller."""
    path = _path(settings, save_id)
    return _act(
        path,
        data,
        SignMineSale(
            _actor(path), mine_id, body.deal_kind, body.volume_t_year, body.months, body.years
        ),
    )


@router.post(
    "/mines/{mine_id}/care",
    response_model=MinesActionOut,
    responses=ERRORS,
    operation_id="careMaintenance",
)
def care_maintenance(
    save_id: str, mine_id: int, body: CareIn, settings: SettingsDep, data: DataDep
) -> MinesActionOut:
    """35.4: care and maintenance, or a restart."""
    path = _path(settings, save_id)
    return _act(path, data, CareMaintenance(_actor(path), mine_id, body.restart))


@router.post(
    "/mines/{mine_id}/close",
    response_model=MinesActionOut,
    responses=ERRORS,
    operation_id="closeMine",
)
def close_mine(save_id: str, mine_id: int, settings: SettingsDep, data: DataDep) -> MinesActionOut:
    path = _path(settings, save_id)
    return _act(path, data, CloseMine(_actor(path), mine_id))


@router.post(
    "/mines/bids/{bid_id}",
    response_model=MinesActionOut,
    responses=ERRORS,
    operation_id="answerRivalBid",
)
def answer_rival_bid(
    save_id: str, bid_id: int, body: BidAnswerIn, settings: SettingsDep, data: DataDep
) -> MinesActionOut:
    """35.5: accept or decline a rival's bid."""
    path = _path(settings, save_id)
    return _act(path, data, AnswerRivalBid(_actor(path), bid_id, body.accept))
