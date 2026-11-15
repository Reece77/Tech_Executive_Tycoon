"""Save-scoped routes for power (M32, docs/formulas.md 46): the Power screen, plant pages, the
siting panel on build screens, quotes, and the founder's power actions (order a plant, sign a
PPA; a PPA is terminated through /contracts/terminate with kind `ppa`). Actions run through
`repository.run_action` with the founder as actor."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from tst.api import power_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.power import (
    BuildPlantIn,
    PlantQuoteOut,
    PowerActionOut,
    PowerPlantOut,
    PowerScreenOut,
    PpaQuoteOut,
    SignPpaIn,
    SitingOut,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.group.assets import group_ids
from tst.sim.power import plants
from tst.sim.power.actions import BuildPlant, SignPpa

router = APIRouter(prefix="/api/saves/{save_id}", tags=["power"])


def _power(path: Path, data: LoadedData) -> PowerScreenOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return power_views.power_out(state, data)


def _act(path: Path, data: LoadedData, action: Action) -> PowerActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return PowerActionOut(
        power=_power(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get("/power", response_model=PowerScreenOut, responses=ERRORS, operation_id="getPower")
def get_power(save_id: str, settings: SettingsDep, data: DataDep) -> PowerScreenOut:
    """Energy by region (demand, supply mix, cost, emissions), plants, contracts, queues,
    outages that happened, plant types' published costs and the generators to contract with."""
    return _power(_path(settings, save_id), data)


@router.get(
    "/power/plants/{facility_id}",
    response_model=PowerPlantOut,
    responses=ERRORS,
    operation_id="getPowerPlant",
)
def get_plant(
    save_id: str, facility_id: int, settings: SettingsDep, data: DataDep
) -> PowerPlantOut:
    state = _state(_path(settings, save_id))
    p = plants.plant_of(state, facility_id)
    if p is None or p.company_id not in group_ids(state):
        raise HTTPException(status_code=404, detail=f"no plant {facility_id}")
    return power_views.plant_out(state, p, data.balance, data.game_data)


@router.get("/power/siting", response_model=SitingOut, responses=ERRORS, operation_id="getSiting")
def get_siting(
    save_id: str, kind: str, capacity: float, settings: SettingsDep, data: DataDep
) -> SitingOut:
    """46.6: each candidate city's grid price, queue wait, carbon price, outage rate and
    behind-the-meter option for a data centre or fab of `kind` and `capacity`."""
    return power_views.siting_out(_state(_path(settings, save_id)), data, kind, capacity)


@router.get(
    "/power/quote/plant",
    response_model=PlantQuoteOut,
    responses=ERRORS,
    operation_id="quotePowerPlant",
)
def quote_plant(
    save_id: str,
    plant_type: str,
    mw: float,
    region: str,
    settings: SettingsDep,
    data: DataDep,
    site_id: int | None = None,
) -> PlantQuoteOut:
    state = _state(_path(settings, save_id))
    if data.game_data.power is None or plant_type not in {
        t.key for t in data.game_data.power.plant_types
    }:
        raise HTTPException(status_code=422, detail=f"unknown plant type {plant_type!r}")
    return power_views.plant_quote_out(
        state, data, _founder_id(state), plant_type, mw, region, site_id
    )


@router.get(
    "/power/quote/ppa", response_model=PpaQuoteOut, responses=ERRORS, operation_id="quotePpa"
)
def quote_ppa(
    save_id: str,
    region: str,
    producer: str,
    mwh_month: float,
    years: int,
    settings: SettingsDep,
    data: DataDep,
) -> PpaQuoteOut:
    state = _state(_path(settings, save_id))
    return power_views.ppa_quote_out(state, data, region, producer, mwh_month, years)


@router.post(
    "/power/plants", response_model=PowerActionOut, responses=ERRORS, operation_id="buildPowerPlant"
)
def build_plant(
    save_id: str, body: BuildPlantIn, settings: SettingsDep, data: DataDep
) -> PowerActionOut:
    path = _path(settings, save_id)
    action = BuildPlant(
        _founder_id(_state(path)), body.plant_type, body.mw, body.region, body.city, body.site_id
    )
    return _act(path, data, action)


@router.post("/power/ppas", response_model=PowerActionOut, responses=ERRORS, operation_id="signPpa")
def sign_ppa(save_id: str, body: SignPpaIn, settings: SettingsDep, data: DataDep) -> PowerActionOut:
    path = _path(settings, save_id)
    action = SignPpa(
        _founder_id(_state(path)), body.region, body.producer, body.mwh_month, body.years
    )
    return _act(path, data, action)
