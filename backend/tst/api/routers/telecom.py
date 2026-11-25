"""Save-scoped routes for telecom (M53, docs/formulas.md 62): the Telecom screen (subscribers,
coverage by region and generation, capacity and quality, spectrum holdings, equipment by vendor,
auctions, bans) and the founder's telecom actions. Mobile, broadband, wholesale and equipment lines
are created, priced and launched through the product routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import telecom_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.telecom import (
    CableIn,
    FibreIn,
    LineSettingIn,
    RadiosIn,
    ReplaceRadiosIn,
    SpectrumBidIn,
    TelecomActionOut,
    TelecomScreenOut,
    TowersIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.telecom.actions import (
    AddRadios,
    BidSpectrum,
    BuildCable,
    BuildFibre,
    BuildTowers,
    ReplaceRadios,
    SetTelecomLine,
)

router = APIRouter(prefix="/api/saves/{save_id}", tags=["telecom"])


def _telecom(path: Path, data: LoadedData) -> TelecomScreenOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return telecom_views.telecom_out(state, data)


def _act(path: Path, data: LoadedData, action: Action) -> TelecomActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return TelecomActionOut(
        telecom=_telecom(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get(
    "/telecom", response_model=TelecomScreenOut, responses=ERRORS, operation_id="getTelecom"
)
def get_telecom(save_id: str, settings: SettingsDep, data: DataDep) -> TelecomScreenOut:
    """Subscribers, coverage, capacity, spectrum, equipment, auctions and bans."""
    return _telecom(_path(settings, save_id), data)


@router.post(
    "/telecom/towers", response_model=TelecomActionOut, responses=ERRORS, operation_id="buildTowers"
)
def build_towers(
    save_id: str, body: TowersIn, settings: SettingsDep, data: DataDep
) -> TelecomActionOut:
    path = _path(settings, save_id)
    action = BuildTowers(
        _founder_id(_state(path)), body.region, body.sites, body.generation, body.vendor, body.city
    )
    return _act(path, data, action)


@router.post(
    "/telecom/radios", response_model=TelecomActionOut, responses=ERRORS, operation_id="addRadios"
)
def add_radios(
    save_id: str, body: RadiosIn, settings: SettingsDep, data: DataDep
) -> TelecomActionOut:
    path = _path(settings, save_id)
    action = AddRadios(
        _founder_id(_state(path)), body.region, body.sites, body.generation, body.vendor
    )
    return _act(path, data, action)


@router.post(
    "/telecom/fibre", response_model=TelecomActionOut, responses=ERRORS, operation_id="buildFibre"
)
def build_fibre(
    save_id: str, body: FibreIn, settings: SettingsDep, data: DataDep
) -> TelecomActionOut:
    path = _path(settings, save_id)
    return _act(
        path, data, BuildFibre(_founder_id(_state(path)), body.region, body.homes, body.city)
    )


@router.post(
    "/telecom/cables", response_model=TelecomActionOut, responses=ERRORS, operation_id="buildCable"
)
def build_cable(
    save_id: str, body: CableIn, settings: SettingsDep, data: DataDep
) -> TelecomActionOut:
    path = _path(settings, save_id)
    action = BuildCable(
        _founder_id(_state(path)), body.name, tuple(body.regions), body.km, body.tbps
    )
    return _act(path, data, action)


@router.post(
    "/telecom/auctions/{auction_id}/bid",
    response_model=TelecomActionOut,
    responses=ERRORS,
    operation_id="bidSpectrum",
)
def bid_spectrum(
    save_id: str, auction_id: int, body: SpectrumBidIn, settings: SettingsDep, data: DataDep
) -> TelecomActionOut:
    path = _path(settings, save_id)
    action = BidSpectrum(_founder_id(_state(path)), auction_id, body.blocks, body.limit_cents)
    return _act(path, data, action)


@router.post(
    "/telecom/radios/{facility_id}/replace",
    response_model=TelecomActionOut,
    responses=ERRORS,
    operation_id="replaceRadios",
)
def replace_radios(
    save_id: str, facility_id: int, body: ReplaceRadiosIn, settings: SettingsDep, data: DataDep
) -> TelecomActionOut:
    path = _path(settings, save_id)
    action = ReplaceRadios(_founder_id(_state(path)), facility_id, body.vendor, body.sites)
    return _act(path, data, action)


@router.post(
    "/telecom/lines/{product_id}",
    response_model=TelecomActionOut,
    responses=ERRORS,
    operation_id="setTelecomLine",
)
def set_line(
    save_id: str, product_id: int, body: LineSettingIn, settings: SettingsDep, data: DataDep
) -> TelecomActionOut:
    path = _path(settings, save_id)
    action = SetTelecomLine(
        _founder_id(_state(path)), product_id, body.zero_rating, body.satellite_partner
    )
    return _act(path, data, action)
