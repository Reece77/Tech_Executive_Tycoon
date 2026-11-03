"""Save-scoped Hardware routes (M12b, formulas.md 26): assembly plants, contract-manufacturing
and wafer contracts, chips, selling spare plant capacity, and a product's BOM and
manufacturing panel. Actions run through `repository.run_action` with the founder as actor
(ADR-0014)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import hardware_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.facilities import _stored
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.hardware import (
    CmContractIn,
    HardwareActionOut,
    HardwareOut,
    ManufacturingOut,
    PlantIn,
    PlantStaffIn,
    WaferContractIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import (
    Action,
    BuildFacility,
    SellFacility,
    SellPlantCapacity,
    SignManufacturingContract,
    SignWaferContract,
    StaffFacility,
)
from tst.sim.errors import FacilityRuleError, ProductRuleError
from tst.sim.state import GameState

router = APIRouter(prefix="/api/saves/{save_id}", tags=["hardware"])


def _out(path: Path, state: GameState, data: LoadedData) -> HardwareOut:
    return hardware_views.hardware_out(state, data, _stored(path, state, data))


def _act(path: Path, data: LoadedData, action: Action) -> HardwareActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return HardwareActionOut(
        hardware=_out(path, state, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get("/hardware", response_model=HardwareOut, responses=ERRORS, operation_id="getHardware")
def get_hardware(save_id: str, settings: SettingsDep, data: DataDep) -> HardwareOut:
    """The Hardware screen: plants, contracts, contract-manufacturing sales, chips, and the
    wafer and component indexes (26.5)."""
    path = _path(settings, save_id)
    return _out(path, _state(path), data)


@router.get(
    "/products/{product_id}/manufacturing",
    response_model=ManufacturingOut,
    responses=ERRORS,
    operation_id="getProductManufacturing",
)
def get_manufacturing(
    save_id: str, product_id: int, settings: SettingsDep, data: DataDep
) -> ManufacturingOut:
    """A device, server or chip product's bill of materials and manufacturing panel."""
    state = _state(_path(settings, save_id))
    product = state.product(product_id)
    if product is None or product.company_id != state.player.id:
        raise ProductRuleError(f"no product {product_id}")
    if not data.game_data.category(product.category).sells_units:
        raise ProductRuleError(f"{product.name} is not a hardware product")
    return hardware_views.manufacturing_out(state, product, data)


@router.post(
    "/hardware/contracts",
    response_model=HardwareActionOut,
    responses=ERRORS,
    operation_id="signManufacturingContract",
)
def sign_cm(
    save_id: str, body: CmContractIn, settings: SettingsDep, data: DataDep
) -> HardwareActionOut:
    path = _path(settings, save_id)
    action = SignManufacturingContract(
        _founder_id(_state(path)),
        body.product_id,
        body.manufacturer,
        body.city,
        body.units,
        body.months,
    )
    return _act(path, data, action)


@router.post(
    "/hardware/wafer-contracts",
    response_model=HardwareActionOut,
    responses=ERRORS,
    operation_id="signWaferContract",
)
def sign_wafer(
    save_id: str, body: WaferContractIn, settings: SettingsDep, data: DataDep
) -> HardwareActionOut:
    path = _path(settings, save_id)
    action = SignWaferContract(
        _founder_id(_state(path)), body.product_id, body.foundry, body.wafers, body.months
    )
    return _act(path, data, action)


@router.post(
    "/hardware/plants",
    response_model=HardwareActionOut,
    responses=ERRORS,
    operation_id="buildPlant",
)
def build_plant(
    save_id: str, body: PlantIn, settings: SettingsDep, data: DataDep
) -> HardwareActionOut:
    """Order an assembly plant in a city (26.2)."""
    path = _path(settings, save_id)
    g = data.game_data
    if not g.has_city(body.city):
        raise FacilityRuleError(f"unknown city {body.city!r}")
    region = g.city(body.city).region
    action = BuildFacility(
        _founder_id(_state(path)),
        data.balance.hardware.plant_kind,
        region,
        body.units,
        None,
        body.city,
    )
    return _act(path, data, action)


@router.post(
    "/hardware/plants/{facility_id}/staff",
    response_model=HardwareActionOut,
    responses=ERRORS,
    operation_id="staffPlant",
)
def staff_plant(
    save_id: str, facility_id: int, body: PlantStaffIn, settings: SettingsDep, data: DataDep
) -> HardwareActionOut:
    path = _path(settings, save_id)
    return _act(path, data, StaffFacility(_founder_id(_state(path)), facility_id, body.unit_id))


@router.post(
    "/hardware/plants/{facility_id}/sell",
    response_model=HardwareActionOut,
    responses=ERRORS,
    operation_id="sellPlant",
)
def sell_plant(
    save_id: str, facility_id: int, settings: SettingsDep, data: DataDep
) -> HardwareActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SellFacility(_founder_id(_state(path)), facility_id))


@router.post(
    "/hardware/contract-manufacturing",
    response_model=HardwareActionOut,
    responses=ERRORS,
    operation_id="sellPlantCapacity",
)
def sell_plant_capacity(save_id: str, settings: SettingsDep, data: DataDep) -> HardwareActionOut:
    """Start selling spare plant capacity as contract manufacturing (26.2)."""
    path = _path(settings, save_id)
    return _act(path, data, SellPlantCapacity(_founder_id(_state(path))))
