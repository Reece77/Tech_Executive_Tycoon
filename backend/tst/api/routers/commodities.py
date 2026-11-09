"""Save-scoped Commodities routes (M17, formulas.md 33): prices, power by region, deals and
suppliers for the Market screen's Commodities tab; quotes; signing a commodity contract or an
offtake. Actions run through `repository.run_action` with the founder as actor (ADR-0014)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import commodity_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.facilities import _stored
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.commodities import (
    CommoditiesActionOut,
    CommoditiesOut,
    CommodityContractIn,
    DealQuoteOut,
    OfftakeIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.actions.commodities import SignCommodityContract, SignOfftake
from tst.sim.commodities import offtake
from tst.sim.state import GameState

router = APIRouter(prefix="/api/saves/{save_id}", tags=["commodities"])


def _out(path: Path, state: GameState, data: LoadedData) -> CommoditiesOut:
    return commodity_views.commodities_out(state, data, _stored(path, state, data), state.player.id)


def _act(path: Path, data: LoadedData, action: Action) -> CommoditiesActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return CommoditiesActionOut(
        commodities=_out(path, state, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get(
    "/commodities", response_model=CommoditiesOut, responses=ERRORS, operation_id="getCommodities"
)
def get_commodities(save_id: str, settings: SettingsDep, data: DataDep) -> CommoditiesOut:
    """The Commodities tab: twelve commodities' prices to this month, power by region, the
    company's contracts and offtakes, and the suppliers (33)."""
    path = _path(settings, save_id)
    return _out(path, _state(path), data)


@router.post(
    "/commodities/offtakes/quote",
    response_model=DealQuoteOut,
    responses=ERRORS,
    operation_id="quoteOfftake",
)
def quote_offtake(
    save_id: str, body: OfftakeIn, settings: SettingsDep, data: DataDep
) -> DealQuoteOut:
    """An offtake's collar, year-1 value and prepayment at this month's spot (33.3)."""
    state = _state(_path(settings, save_id))
    q = offtake.offtake_quote(
        state,
        body.good,
        body.supplier,
        body.years,
        body.volume_year,
        body.prepay,
        data.balance,
        data.game_data,
    )
    return DealQuoteOut(
        good=q.good,
        supplier=q.supplier,
        months=q.months,
        volume_year=q.volume_year,
        price=q.price,
        floor=q.floor,
        ceiling=q.ceiling,
        year_value_cents=q.year_value_cents,
        prepaid_cents=q.prepaid_cents,
    )


@router.post(
    "/commodities/offtakes",
    response_model=CommoditiesActionOut,
    responses=ERRORS,
    operation_id="signOfftake",
)
def sign_offtake(
    save_id: str, body: OfftakeIn, settings: SettingsDep, data: DataDep
) -> CommoditiesActionOut:
    """Sign an offtake agreement (energy 5, 33.3)."""
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    action = SignOfftake(
        founder, body.good, body.supplier, body.years, body.volume_year, body.prepay
    )
    return _act(path, data, action)


@router.post(
    "/commodities/contracts",
    response_model=CommoditiesActionOut,
    responses=ERRORS,
    operation_id="signCommodityContract",
)
def sign_contract(
    save_id: str, body: CommodityContractIn, settings: SettingsDep, data: DataDep
) -> CommoditiesActionOut:
    """Sign a fixed-price commodity contract (energy 6, 33.3)."""
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    action = SignCommodityContract(founder, body.good, body.months, body.volume_year)
    return _act(path, data, action)
