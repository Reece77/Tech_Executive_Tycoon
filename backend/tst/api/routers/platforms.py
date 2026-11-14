"""Save-scoped routes for platforms (M31, docs/formulas.md 44): the Platforms screen and the
founder's platform actions (a device line's platform, an own store's rules, developer
platforms, open source, steering, complying with a removal, adopting a standard). Actions run
through `repository.run_action` with the founder as actor."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import platform_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.platforms import (
    AdoptIn,
    DevicePlatformIn,
    OpenSourceIn,
    PlatformRulesIn,
    PlatformsActionOut,
    PlatformsOut,
    ProductIn,
    SteeringIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.platforms.actions import (
    AdoptStandard,
    ComplyListing,
    CreateDeveloperPlatform,
    OpenSourceProduct,
    SetDevicePlatform,
    SetPlatformRules,
    SetSteering,
)

router = APIRouter(prefix="/api/saves/{save_id}", tags=["platforms"])


def _platforms(path: Path, data: LoadedData) -> PlatformsOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return platform_views.platforms_out(state, data)


def _act(path: Path, data: LoadedData, action: Action) -> PlatformsActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return PlatformsActionOut(
        platforms=_platforms(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get(
    "/platforms", response_model=PlatformsOut, responses=ERRORS, operation_id="getPlatforms"
)
def get_platforms(save_id: str, settings: SettingsDep, data: DataDep) -> PlatformsOut:
    """Every platform's users, developers, catalogue, fees and rules by region; the group's
    device lines, apps (fees and listings) and standards (44.10)."""
    return _platforms(_path(settings, save_id), data)


@router.post(
    "/platforms/device-platform",
    response_model=PlatformsActionOut,
    responses=ERRORS,
    operation_id="setDevicePlatform",
)
def set_device_platform(
    save_id: str, body: DevicePlatformIn, settings: SettingsDep, data: DataDep
) -> PlatformsActionOut:
    path = _path(settings, save_id)
    action = SetDevicePlatform(_founder_id(_state(path)), body.product_id, body.platform_id)
    return _act(path, data, action)


@router.post(
    "/platforms/rules",
    response_model=PlatformsActionOut,
    responses=ERRORS,
    operation_id="setPlatformRules",
)
def set_platform_rules(
    save_id: str, body: PlatformRulesIn, settings: SettingsDep, data: DataDep
) -> PlatformsActionOut:
    path = _path(settings, save_id)
    action = SetPlatformRules(
        _founder_id(_state(path)),
        body.platform_id,
        fee=body.fee,
        strictness=body.strictness,
        self_pref=body.self_pref,
        anti_steering=body.anti_steering,
        side_loading=body.side_loading,
        licence_cents=body.licence_cents,
        stop_licensing=body.stop_licensing,
    )
    return _act(path, data, action)


@router.post(
    "/platforms/developer",
    response_model=PlatformsActionOut,
    responses=ERRORS,
    operation_id="createDeveloperPlatform",
)
def create_developer_platform(
    save_id: str, body: ProductIn, settings: SettingsDep, data: DataDep
) -> PlatformsActionOut:
    path = _path(settings, save_id)
    return _act(path, data, CreateDeveloperPlatform(_founder_id(_state(path)), body.product_id))


@router.post(
    "/platforms/open-source",
    response_model=PlatformsActionOut,
    responses=ERRORS,
    operation_id="openSourceProduct",
)
def open_source(
    save_id: str, body: OpenSourceIn, settings: SettingsDep, data: DataDep
) -> PlatformsActionOut:
    path = _path(settings, save_id)
    action = OpenSourceProduct(_founder_id(_state(path)), body.product_id, body.open)
    return _act(path, data, action)


@router.post(
    "/platforms/steering",
    response_model=PlatformsActionOut,
    responses=ERRORS,
    operation_id="setSteering",
)
def set_steering(
    save_id: str, body: SteeringIn, settings: SettingsDep, data: DataDep
) -> PlatformsActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SetSteering(_founder_id(_state(path)), body.product_id, body.on))


@router.post(
    "/platforms/comply",
    response_model=PlatformsActionOut,
    responses=ERRORS,
    operation_id="complyListing",
)
def comply(
    save_id: str, body: ProductIn, settings: SettingsDep, data: DataDep
) -> PlatformsActionOut:
    path = _path(settings, save_id)
    return _act(path, data, ComplyListing(_founder_id(_state(path)), body.product_id))


@router.post(
    "/platforms/adopt",
    response_model=PlatformsActionOut,
    responses=ERRORS,
    operation_id="adoptStandard",
)
def adopt(save_id: str, body: AdoptIn, settings: SettingsDep, data: DataDep) -> PlatformsActionOut:
    path = _path(settings, save_id)
    action = AdoptStandard(_founder_id(_state(path)), body.product_id, body.standard_id)
    return _act(path, data, action)
