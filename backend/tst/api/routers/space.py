"""Save-scoped routes for space and satellites (M40, docs/formulas.md 56): the Space screen
(vehicles, launches, cost a kg, constellations and coverage, subscribers by region, licences,
rivals' public launches and constellations) and the founder's space actions. Launch, broadband and
Earth-observation lines are created, priced and launched through the product routes; launch sites
and satellite plants through the facility routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import space_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.space import (
    ConstellationIn,
    ConstellationPlanIn,
    D2dPartnerIn,
    LaunchSpecIn,
    SpaceActionOut,
    SpaceLicenceIn,
    SpaceScreenOut,
    TerminalPriceIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.space.actions import (
    ApplyLicence,
    PlanConstellation,
    SetConstellationPlan,
    SetD2dPartner,
    SetLaunchSpec,
    SetTerminalPrice,
)

router = APIRouter(prefix="/api/saves/{save_id}", tags=["space"])


def _space(path: Path, data: LoadedData) -> SpaceScreenOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return space_views.space_out(state, data)


def _act(path: Path, data: LoadedData, action: Action) -> SpaceActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return SpaceActionOut(
        space=_space(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get("/space", response_model=SpaceScreenOut, responses=ERRORS, operation_id="getSpace")
def get_space(save_id: str, settings: SettingsDep, data: DataDep) -> SpaceScreenOut:
    """Vehicles and launches, cost a kg, constellations and coverage, subscribers by region,
    licences and rivals' public launches and constellations."""
    return _space(_path(settings, save_id), data)


@router.post(
    "/space/vehicles/{product_id}/spec",
    response_model=SpaceActionOut,
    responses=ERRORS,
    operation_id="setLaunchSpec",
)
def set_launch_spec(
    save_id: str, product_id: int, body: LaunchSpecIn, settings: SettingsDep, data: DataDep
) -> SpaceActionOut:
    path = _path(settings, save_id)
    action = SetLaunchSpec(_founder_id(_state(path)), product_id, body.payload_kg, body.reuse)
    return _act(path, data, action)


@router.post(
    "/space/constellations",
    response_model=SpaceActionOut,
    responses=ERRORS,
    operation_id="planConstellation",
)
def plan_constellation(
    save_id: str, body: ConstellationIn, settings: SettingsDep, data: DataDep
) -> SpaceActionOut:
    path = _path(settings, save_id)
    action = PlanConstellation(
        actor_id=_founder_id(_state(path)),
        name=body.name,
        constellation_kind=body.kind,
        product_id=body.product_id,
        shells=body.shells,
        mass_kg=body.mass_kg,
        life_months=body.life_months,
        build_per_month=body.build_per_month,
        launches_per_month=body.launches_per_month,
        vehicle_product_id=body.vehicle_product_id,
        d2d=body.d2d,
        insured=body.insured,
    )
    return _act(path, data, action)


@router.post(
    "/space/constellations/{constellation_id}/plan",
    response_model=SpaceActionOut,
    responses=ERRORS,
    operation_id="setConstellationPlan",
)
def set_constellation_plan(
    save_id: str,
    constellation_id: int,
    body: ConstellationPlanIn,
    settings: SettingsDep,
    data: DataDep,
) -> SpaceActionOut:
    path = _path(settings, save_id)
    action = SetConstellationPlan(
        _founder_id(_state(path)),
        constellation_id,
        body.shells,
        body.build_per_month,
        body.launches_per_month,
        body.vehicle_product_id,
        body.insured,
    )
    return _act(path, data, action)


@router.post(
    "/space/licences", response_model=SpaceActionOut, responses=ERRORS, operation_id="applyLicence"
)
def apply_licence(
    save_id: str, body: SpaceLicenceIn, settings: SettingsDep, data: DataDep
) -> SpaceActionOut:
    path = _path(settings, save_id)
    return _act(path, data, ApplyLicence(_founder_id(_state(path)), body.region))


@router.post(
    "/space/broadband/{product_id}/terminal",
    response_model=SpaceActionOut,
    responses=ERRORS,
    operation_id="setTerminalPrice",
)
def set_terminal_price(
    save_id: str, product_id: int, body: TerminalPriceIn, settings: SettingsDep, data: DataDep
) -> SpaceActionOut:
    path = _path(settings, save_id)
    action = SetTerminalPrice(_founder_id(_state(path)), product_id, body.price_cents)
    return _act(path, data, action)


@router.post(
    "/space/broadband/{product_id}/d2d",
    response_model=SpaceActionOut,
    responses=ERRORS,
    operation_id="setD2dPartner",
)
def set_d2d_partner(
    save_id: str, product_id: int, body: D2dPartnerIn, settings: SettingsDep, data: DataDep
) -> SpaceActionOut:
    path = _path(settings, save_id)
    action = SetD2dPartner(_founder_id(_state(path)), product_id, body.partner)
    return _act(path, data, action)
