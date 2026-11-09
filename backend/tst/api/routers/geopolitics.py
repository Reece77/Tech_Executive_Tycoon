"""Save-scoped routes for geopolitics (M22, formulas.md 39): the World screen and the founder's
export-control actions (licence requests, selling through distributors, compliant variants,
local partners). Actions run through `repository.run_action` with the founder as actor."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import geopolitics_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.geopolitics import (
    GreyRouteIn,
    LicenceIn,
    PartnerIn,
    VariantIn,
    WorldActionOut,
    WorldOut,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.geopolitics.actions import (
    LaunchVariant,
    RequestLicence,
    SetGreyRoute,
    TakeLocalPartner,
)

router = APIRouter(prefix="/api/saves/{save_id}", tags=["geopolitics"])


def _world(path: Path, data: LoadedData) -> WorldOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return geopolitics_views.world_out(state, data)


def _act(path: Path, data: LoadedData, action: Action) -> WorldActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return WorldActionOut(
        world=_world(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get("/world", response_model=WorldOut, responses=ERRORS, operation_id="getWorld")
def get_world(save_id: str, settings: SettingsDep, data: DataDep) -> WorldOut:
    """Blocs, tension, the export rules announced so far, licences, variants, the entity list
    and the group's exposure (39). Nothing before it is announced."""
    return _world(_path(settings, save_id), data)


@router.post(
    "/world/licence", response_model=WorldActionOut, responses=ERRORS, operation_id="requestLicence"
)
def request_licence(
    save_id: str, body: LicenceIn, settings: SettingsDep, data: DataDep
) -> WorldActionOut:
    path = _path(settings, save_id)
    action = RequestLicence(_founder_id(_state(path)), body.product_id, body.country)
    return _act(path, data, action)


@router.post(
    "/world/grey", response_model=WorldActionOut, responses=ERRORS, operation_id="setGreyRoute"
)
def set_grey_route(
    save_id: str, body: GreyRouteIn, settings: SettingsDep, data: DataDep
) -> WorldActionOut:
    path = _path(settings, save_id)
    action = SetGreyRoute(_founder_id(_state(path)), body.product_id, body.country, body.on)
    return _act(path, data, action)


@router.post(
    "/world/variant", response_model=WorldActionOut, responses=ERRORS, operation_id="launchVariant"
)
def launch_variant(
    save_id: str, body: VariantIn, settings: SettingsDep, data: DataDep
) -> WorldActionOut:
    path = _path(settings, save_id)
    return _act(path, data, LaunchVariant(_founder_id(_state(path)), body.product_id))


@router.post(
    "/world/partner",
    response_model=WorldActionOut,
    responses=ERRORS,
    operation_id="takeLocalPartner",
)
def take_local_partner(
    save_id: str, body: PartnerIn, settings: SettingsDep, data: DataDep
) -> WorldActionOut:
    path = _path(settings, save_id)
    return _act(path, data, TakeLocalPartner(_founder_id(_state(path)), body.company_id))
