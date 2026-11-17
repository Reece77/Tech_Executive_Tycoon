"""Save-scoped routes for robotics and robotaxis (M39, docs/formulas.md 53): the Robotics screen
(robot markets, makers, humanoids, the player's robot lines and plant automation) and the Mobility
screen (robotaxi cities, rival services, the player's zones, fleets, depots and incidents), and the
founder's robotics actions. A robot line or a robotaxi service is created, priced and launched
through the product routes; plants through the facility routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import robotics_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.robotics import (
    AddCarsIn,
    BuildDepotIn,
    HumanoidSpecIn,
    InstallRobotsIn,
    MobilityActionOut,
    MobilityScreenOut,
    OpenZoneIn,
    RidePriceIn,
    RoboticsActionOut,
    RoboticsScreenOut,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.robotics.actions import (
    AddRobotaxis,
    BuildDepot,
    CloseZone,
    InstallRobots,
    OpenZone,
    SetHumanoidSpec,
    SetRidePrice,
)
from tst.sim.state import GameState

router = APIRouter(prefix="/api/saves/{save_id}", tags=["robotics"])


def _robotics(path: Path, data: LoadedData) -> RoboticsScreenOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return robotics_views.robotics_out(state, data)


def _mobility(path: Path, data: LoadedData) -> MobilityScreenOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return robotics_views.mobility_out(state, data)


def _run(path: Path, data: LoadedData, action: Action) -> tuple[GameState, int]:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return state, unread


def _act_robotics(path: Path, data: LoadedData, action: Action) -> RoboticsActionOut:
    state, unread = _run(path, data, action)
    return RoboticsActionOut(
        robotics=_robotics(path, data),
        energy=views.energy(state, data),
        unread_inbox=unread,
    )


def _act_mobility(path: Path, data: LoadedData, action: Action) -> MobilityActionOut:
    state, unread = _run(path, data, action)
    return MobilityActionOut(
        mobility=_mobility(path, data),
        energy=views.energy(state, data),
        unread_inbox=unread,
    )


@router.get(
    "/robotics", response_model=RoboticsScreenOut, responses=ERRORS, operation_id="getRobotics"
)
def get_robotics(save_id: str, settings: SettingsDep, data: DataDep) -> RoboticsScreenOut:
    """Robot installations by region, makers' lines and shares, the humanoid market, and the
    player's robot lines and plant automation."""
    return _robotics(_path(settings, save_id), data)


@router.post(
    "/robotics/plants/{facility_id}/robots",
    response_model=RoboticsActionOut,
    responses=ERRORS,
    operation_id="installRobots",
)
def install_robots(
    save_id: str, facility_id: int, body: InstallRobotsIn, settings: SettingsDep, data: DataDep
) -> RoboticsActionOut:
    path = _path(settings, save_id)
    action = InstallRobots(_founder_id(_state(path)), facility_id, body.robots, body.product_id)
    return _act_robotics(path, data, action)


@router.post(
    "/robotics/humanoids/{product_id}/spec",
    response_model=RoboticsActionOut,
    responses=ERRORS,
    operation_id="setHumanoidSpec",
)
def set_humanoid_spec(
    save_id: str, product_id: int, body: HumanoidSpecIn, settings: SettingsDep, data: DataDep
) -> RoboticsActionOut:
    path = _path(settings, save_id)
    action = SetHumanoidSpec(
        _founder_id(_state(path)), product_id, body.ai_product_id, body.chip_product_id
    )
    return _act_robotics(path, data, action)


@router.get(
    "/mobility", response_model=MobilityScreenOut, responses=ERRORS, operation_id="getMobility"
)
def get_mobility(save_id: str, settings: SettingsDep, data: DataDep) -> MobilityScreenOut:
    """Robotaxi cities, rival services, and the player's zones, fleets, depots and incidents."""
    return _mobility(_path(settings, save_id), data)


@router.post(
    "/mobility/zones", response_model=MobilityActionOut, responses=ERRORS, operation_id="openZone"
)
def open_zone(
    save_id: str, body: OpenZoneIn, settings: SettingsDep, data: DataDep
) -> MobilityActionOut:
    path = _path(settings, save_id)
    action = OpenZone(
        _founder_id(_state(path)), body.product_id, body.city, body.size, body.price_cents
    )
    return _act_mobility(path, data, action)


@router.post(
    "/mobility/zones/{zone_id}/cars",
    response_model=MobilityActionOut,
    responses=ERRORS,
    operation_id="addRobotaxis",
)
def add_cars(
    save_id: str, zone_id: int, body: AddCarsIn, settings: SettingsDep, data: DataDep
) -> MobilityActionOut:
    path = _path(settings, save_id)
    action = AddRobotaxis(_founder_id(_state(path)), zone_id, body.cars, body.car_product_id)
    return _act_mobility(path, data, action)


@router.post(
    "/mobility/zones/{zone_id}/price",
    response_model=MobilityActionOut,
    responses=ERRORS,
    operation_id="setRidePrice",
)
def set_price(
    save_id: str, zone_id: int, body: RidePriceIn, settings: SettingsDep, data: DataDep
) -> MobilityActionOut:
    path = _path(settings, save_id)
    action = SetRidePrice(_founder_id(_state(path)), zone_id, body.price_cents)
    return _act_mobility(path, data, action)


@router.post(
    "/mobility/zones/{zone_id}/close",
    response_model=MobilityActionOut,
    responses=ERRORS,
    operation_id="closeZone",
)
def close_zone(
    save_id: str, zone_id: int, settings: SettingsDep, data: DataDep
) -> MobilityActionOut:
    path = _path(settings, save_id)
    return _act_mobility(path, data, CloseZone(_founder_id(_state(path)), zone_id))


@router.post(
    "/mobility/depots",
    response_model=MobilityActionOut,
    responses=ERRORS,
    operation_id="buildDepot",
)
def build_depot(
    save_id: str, body: BuildDepotIn, settings: SettingsDep, data: DataDep
) -> MobilityActionOut:
    path = _path(settings, save_id)
    action = BuildDepot(_founder_id(_state(path)), body.city, body.cars)
    return _act_mobility(path, data, action)
