"""Save-scoped geography routes (M9, formulas.md 19): cities and offices, units' offices,
and a product's regions. Actions run through `repository.run_action` with the founder as
actor (ADR-0014)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Query

from tst.api import geo_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.geo import (
    GeoActionOut,
    GeoOut,
    LaunchRegionIn,
    LeaseIn,
    LeasePreviewOut,
    MarketingSplitIn,
    ProductRegionsActionOut,
    ProductRegionsOut,
    RegionalPriceIn,
    UnitOfficeIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.actions.geo import (
    CloseOffice,
    LaunchInRegion,
    LeaseOffice,
    SetMarketingSplit,
    SetRegionalPrice,
    SetUnitOffice,
)
from tst.sim.geo.cities import hq_city

router = APIRouter(prefix="/api/saves/{save_id}", tags=["geo"])


def _unread(path: Path, company_id: int) -> int:
    with repository.open_session(path) as session:
        return inbox.unread_count(session, company_id)


def _geo_act(path: Path, data: LoadedData, action: Action) -> GeoActionOut:
    state = repository.run_action(path, data, action).new_state
    return GeoActionOut(
        geo=geo_views.geo_out(state, data),
        energy=views.energy(state, data),
        unread_inbox=_unread(path, state.player.id),
    )


def _regions_act(
    path: Path, data: LoadedData, action: Action, product_id: int
) -> ProductRegionsActionOut:
    state = repository.run_action(path, data, action).new_state
    return ProductRegionsActionOut(
        regions=geo_views.product_regions_out(state, product_id, data),
        energy=views.energy(state, data),
        unread_inbox=_unread(path, state.player.id),
    )


@router.get("/geo", response_model=GeoOut, responses=ERRORS, operation_id="getGeo")
def get_geo(save_id: str, settings: SettingsDep, data: DataDep) -> GeoOut:
    """The Offices screen: flexible HQ space and leases, and every city's indexes."""
    return geo_views.geo_out(_state(_path(settings, save_id)), data)


@router.get(
    "/geo/lease-preview",
    response_model=LeasePreviewOut,
    responses=ERRORS,
    operation_id="previewLease",
)
def preview_lease(
    save_id: str,
    settings: SettingsDep,
    data: DataDep,
    city: Annotated[str | None, Query(description="Default: the HQ city")] = None,
    seats: Annotated[int | None, Query(description="Default: the smallest lease")] = None,
) -> LeasePreviewOut:
    """Rent, fit-out and an example market rate for a lease (the Lease dialog)."""
    state = _state(_path(settings, save_id))
    chosen = city or hq_city(state.player, data.balance)
    return geo_views.lease_preview(chosen, seats or data.balance.office.seat_sizes[0], data)


@router.post(
    "/geo/offices", response_model=GeoActionOut, responses=ERRORS, operation_id="leaseOffice"
)
def lease_office(save_id: str, body: LeaseIn, settings: SettingsDep, data: DataDep) -> GeoActionOut:
    path = _path(settings, save_id)
    action = LeaseOffice(_founder_id(_state(path)), body.city, body.seats)
    return _geo_act(path, data, action)


@router.post(
    "/geo/offices/{office_id}/close",
    response_model=GeoActionOut,
    responses=ERRORS,
    operation_id="closeOffice",
)
def close_office(
    save_id: str, office_id: int, settings: SettingsDep, data: DataDep
) -> GeoActionOut:
    path = _path(settings, save_id)
    return _geo_act(path, data, CloseOffice(_founder_id(_state(path)), office_id))


@router.post(
    "/geo/units/{unit_id}/office",
    response_model=GeoActionOut,
    responses=ERRORS,
    operation_id="setUnitOffice",
)
def set_unit_office(
    save_id: str, unit_id: int, body: UnitOfficeIn, settings: SettingsDep, data: DataDep
) -> GeoActionOut:
    path = _path(settings, save_id)
    action = SetUnitOffice(_founder_id(_state(path)), unit_id, body.office_id)
    return _geo_act(path, data, action)


@router.get(
    "/products/{product_id}/regions",
    response_model=ProductRegionsOut,
    responses=ERRORS,
    operation_id="getProductRegions",
)
def get_product_regions(
    save_id: str, product_id: int, settings: SettingsDep, data: DataDep
) -> ProductRegionsOut:
    """Where a product sells: status, prices, customers and revenue by region, reach, and
    the builders' spread (19.7)."""
    return geo_views.product_regions_out(_state(_path(settings, save_id)), product_id, data)


@router.post(
    "/products/{product_id}/regions",
    response_model=ProductRegionsActionOut,
    responses=ERRORS,
    operation_id="launchInRegion",
)
def launch_in_region(
    save_id: str, product_id: int, body: LaunchRegionIn, settings: SettingsDep, data: DataDep
) -> ProductRegionsActionOut:
    path = _path(settings, save_id)
    action = LaunchInRegion(_founder_id(_state(path)), product_id, body.region)
    return _regions_act(path, data, action, product_id)


@router.post(
    "/products/{product_id}/regions/{region}/price",
    response_model=ProductRegionsActionOut,
    responses=ERRORS,
    operation_id="setRegionalPrice",
)
def set_regional_price(
    save_id: str,
    product_id: int,
    region: str,
    body: RegionalPriceIn,
    settings: SettingsDep,
    data: DataDep,
) -> ProductRegionsActionOut:
    path = _path(settings, save_id)
    action = SetRegionalPrice(
        _founder_id(_state(path)), product_id, region, body.segment, body.price_cents
    )
    return _regions_act(path, data, action, product_id)


@router.post(
    "/products/{product_id}/regions/marketing",
    response_model=ProductRegionsActionOut,
    responses=ERRORS,
    operation_id="setMarketingSplit",
)
def set_marketing_split(
    save_id: str,
    product_id: int,
    body: MarketingSplitIn,
    settings: SettingsDep,
    data: DataDep,
) -> ProductRegionsActionOut:
    """Split the product's marketing across its regions (23.5); empty: back to by revenue."""
    path = _path(settings, save_id)
    shares = tuple(sorted(body.shares.items()))
    action = SetMarketingSplit(_founder_id(_state(path)), product_id, shares)
    return _regions_act(path, data, action, product_id)
