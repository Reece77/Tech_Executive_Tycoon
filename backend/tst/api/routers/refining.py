"""Save-scoped routes for refining (M20, formulas.md 36): the Refineries screen and the
founder's refinery actions (build, staff, sell, contracts). Actions run through
`repository.run_action` with the founder as actor."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

from fastapi import APIRouter

from tst.api import refining_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.refining import (
    BuildRefineryIn,
    RefineriesActionOut,
    RefineriesOut,
    RefineryQuoteOut,
    RefiningDealIn,
    StaffRefineryIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.actions.facilities import SellFacility, StaffFacility
from tst.sim.refining.actions import BuildRefinery, SignRefiningDeal

router = APIRouter(prefix="/api/saves/{save_id}", tags=["refining"])


def _refineries(path: Path, data: LoadedData) -> RefineriesOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return refining_views.refineries_out(state, data)


def _act(path: Path, data: LoadedData, action: Action) -> RefineriesActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return RefineriesActionOut(
        refineries=_refineries(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get(
    "/refineries", response_model=RefineriesOut, responses=ERRORS, operation_id="getRefineries"
)
def get_refineries(save_id: str, settings: SettingsDep, data: DataDep) -> RefineriesOut:
    """The group's plants (inputs, outputs, yield, power cost, unit cost against market,
    margin), recipes, prices, contracts, this month's own supply and the value chain (36)."""
    return _refineries(_path(settings, save_id), data)


@router.get(
    "/refineries/quote",
    response_model=RefineryQuoteOut,
    responses=ERRORS,
    operation_id="quoteRefinery",
)
def quote_refinery(
    save_id: str, recipe: str, region: str, capacity: int, settings: SettingsDep, data: DataDep
) -> RefineryQuoteOut:
    """What a plant would cost to build and to run at full output now (36.1)."""
    state = _state(_path(settings, save_id))
    return refining_views.quote_out(state, recipe, region, capacity, data)


@router.post(
    "/refineries/build",
    response_model=RefineriesActionOut,
    responses=ERRORS,
    operation_id="buildRefinery",
)
def build_refinery(
    save_id: str, body: BuildRefineryIn, settings: SettingsDep, data: DataDep
) -> RefineriesActionOut:
    path = _path(settings, save_id)
    actor = _founder_id(_state(path))
    action = BuildRefinery(
        actor, body.recipe, body.region, body.capacity, body.host_id, body.city, body.company_id
    )
    return _act(path, data, action)


@router.post(
    "/refineries/deal",
    response_model=RefineriesActionOut,
    responses=ERRORS,
    operation_id="signRefiningDeal",
)
def sign_refining_deal(
    save_id: str, body: RefiningDealIn, settings: SettingsDep, data: DataDep
) -> RefineriesActionOut:
    path = _path(settings, save_id)
    actor = _founder_id(_state(path))
    side = cast(Literal["buy", "sell"], body.side)
    return _act(path, data, SignRefiningDeal(actor, side, body.good, body.months, body.volume))


@router.post(
    "/refineries/{facility_id}/staff",
    response_model=RefineriesActionOut,
    responses=ERRORS,
    operation_id="staffRefinery",
)
def staff_refinery(
    save_id: str, facility_id: int, body: StaffRefineryIn, settings: SettingsDep, data: DataDep
) -> RefineriesActionOut:
    path = _path(settings, save_id)
    return _act(path, data, StaffFacility(_founder_id(_state(path)), facility_id, body.unit_id))


@router.post(
    "/refineries/{facility_id}/sell",
    response_model=RefineriesActionOut,
    responses=ERRORS,
    operation_id="sellRefinery",
)
def sell_refinery(
    save_id: str, facility_id: int, settings: SettingsDep, data: DataDep
) -> RefineriesActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SellFacility(_founder_id(_state(path)), facility_id))
