"""Save-scoped routes for electric vehicles (M38, docs/formulas.md 49): the Vehicles screen
(markets, battery prices, rivals, the player's cars, plants and networks) and the founder's
vehicle actions (a car's design, a cell plant, a charging network and its access). A car line is
created and priced through the product routes, a vehicle plant through the facility routes (kind
`vehicle_plant`) and contract assembly through the hardware routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from tst.api import vehicle_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.vehicles import (
    BuildCellPlantIn,
    BuildChargingIn,
    ChargingAccessIn,
    MyCarOut,
    SetVehicleSpecIn,
    VehiclesActionOut,
    VehiclesScreenOut,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.group.assets import group_ids
from tst.sim.vehicles.actions import (
    BuildCellPlant,
    BuildChargingNetwork,
    SetChargingAccess,
    SetVehicleSpec,
)
from tst.sim.vehicles.data import is_vehicle

router = APIRouter(prefix="/api/saves/{save_id}", tags=["vehicles"])


def _vehicles(path: Path, data: LoadedData) -> VehiclesScreenOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return vehicle_views.vehicles_out(state, data)


def _act(path: Path, data: LoadedData, action: Action) -> VehiclesActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return VehiclesActionOut(
        vehicles=_vehicles(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get(
    "/vehicles", response_model=VehiclesScreenOut, responses=ERRORS, operation_id="getVehicles"
)
def get_vehicles(save_id: str, settings: SettingsDep, data: DataDep) -> VehiclesScreenOut:
    """EV markets by region (share, sales, charging, subsidies, tariffs, approvals), battery
    prices, rivals' line-ups and shares, and the player's cars, plants and networks."""
    return _vehicles(_path(settings, save_id), data)


@router.get(
    "/vehicles/cars/{car_id}",
    response_model=MyCarOut,
    responses=ERRORS,
    operation_id="getVehicleCar",
)
def get_car(save_id: str, car_id: int, settings: SettingsDep, data: DataDep) -> MyCarOut:
    """A car line's page; `car_id` is the line's product id (a car line only, as the power
    plants' `facility_id`)."""
    state = _state(_path(settings, save_id))
    p = state.product(car_id)
    if p is None or p.company_id not in group_ids(state) or not is_vehicle(p, data.balance):
        raise HTTPException(status_code=404, detail=f"no car line {car_id}")
    return vehicle_views.car_out(state, p, data)


@router.post(
    "/vehicles/cars/{car_id}/spec",
    response_model=VehiclesActionOut,
    responses=ERRORS,
    operation_id="setVehicleSpec",
)
def set_spec(
    save_id: str, car_id: int, body: SetVehicleSpecIn, settings: SettingsDep, data: DataDep
) -> VehiclesActionOut:
    path = _path(settings, save_id)
    action = SetVehicleSpec(
        _founder_id(_state(path)),
        car_id,
        body.pack_kwh,
        body.chemistry,
        body.charge_kw,
        body.autonomy,
        body.platform,
        body.cells,
        body.os_product_id,
    )
    return _act(path, data, action)


@router.post(
    "/vehicles/cell-plants",
    response_model=VehiclesActionOut,
    responses=ERRORS,
    operation_id="buildCellPlant",
)
def build_cell_plant(
    save_id: str, body: BuildCellPlantIn, settings: SettingsDep, data: DataDep
) -> VehiclesActionOut:
    path = _path(settings, save_id)
    action = BuildCellPlant(
        _founder_id(_state(path)), body.region, body.mwh_month, body.chemistry, body.city
    )
    return _act(path, data, action)


@router.post(
    "/vehicles/charging",
    response_model=VehiclesActionOut,
    responses=ERRORS,
    operation_id="buildChargingNetwork",
)
def build_charging(
    save_id: str, body: BuildChargingIn, settings: SettingsDep, data: DataDep
) -> VehiclesActionOut:
    path = _path(settings, save_id)
    action = BuildChargingNetwork(
        _founder_id(_state(path)), body.region, body.chargers, body.exclusive, body.city
    )
    return _act(path, data, action)


@router.post(
    "/vehicles/charging/{facility_id}/access",
    response_model=VehiclesActionOut,
    responses=ERRORS,
    operation_id="setChargingAccess",
)
def set_access(
    save_id: str, facility_id: int, body: ChargingAccessIn, settings: SettingsDep, data: DataDep
) -> VehiclesActionOut:
    path = _path(settings, save_id)
    action = SetChargingAccess(_founder_id(_state(path)), facility_id, body.exclusive)
    return _act(path, data, action)
