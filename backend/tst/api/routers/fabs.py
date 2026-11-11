"""Save-scoped routes for fabs and process nodes (M21, formulas.md 38): the Fabs screen, the
node timeline (Market screen) and the founder's fab actions (build, convert, staff, sell).
Actions run through `repository.run_action` with the founder as actor."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import fab_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.fabs import (
    BuildFabIn,
    FabQuoteOut,
    FabsActionOut,
    FabsOut,
    FoundryContractIn,
    NodesOut,
    StaffFabIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.actions.facilities import SellFacility, StaffFacility
from tst.sim.fabs.actions import BuildFab, UpgradeFab
from tst.sim.fabs.foundry import SignFoundryContract

router = APIRouter(prefix="/api/saves/{save_id}", tags=["fabs"])


def _fabs(path: Path, data: LoadedData) -> FabsOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return fab_views.fabs_out(state, data)


def _act(path: Path, data: LoadedData, action: Action) -> FabsActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return FabsActionOut(
        fabs=_fabs(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get("/fabs", response_model=FabsOut, responses=ERRORS, operation_id="getFabs")
def get_fabs(save_id: str, settings: SettingsDep, data: DataDep) -> FabsOut:
    """The player's fabs (node, capacity, use, yield curve, cost per good die against the
    market, foundry customers) and the node timeline (38)."""
    return _fabs(_path(settings, save_id), data)


@router.get("/nodes", response_model=NodesOut, responses=ERRORS, operation_id="getNodes")
def get_nodes(save_id: str, settings: SettingsDep, data: DataDep) -> NodesOut:
    """The process-node timeline: nodes in volume and who runs them, future nodes' windows,
    rival foundries and the foundry market (38.1, 38.3)."""
    return fab_views.nodes_out(_state(_path(settings, save_id)), data)


@router.get("/fabs/quote", response_model=FabQuoteOut, responses=ERRORS, operation_id="quoteFab")
def quote_fab(
    save_id: str,
    node: str,
    region: str,
    size: int,
    settings: SettingsDep,
    data: DataDep,
    duv: bool = False,
) -> FabQuoteOut:
    """What a fab would cost, when it could run and what a start would cost (38.2)."""
    state = _state(_path(settings, save_id))
    return fab_views.quote_out(state, node, region, size, duv, data)


@router.post("/fabs/build", response_model=FabsActionOut, responses=ERRORS, operation_id="buildFab")
def build_fab(
    save_id: str, body: BuildFabIn, settings: SettingsDep, data: DataDep
) -> FabsActionOut:
    path = _path(settings, save_id)
    actor = _founder_id(_state(path))
    action = BuildFab(
        actor,
        body.node,
        body.region,
        body.size,
        body.duv,
        body.city,
        company_id=body.company_id,
        country=body.country,
    )
    return _act(path, data, action)


@router.post(
    "/fabs/{facility_id}/upgrade",
    response_model=FabsActionOut,
    responses=ERRORS,
    operation_id="upgradeFab",
)
def upgrade_fab(
    save_id: str, facility_id: int, settings: SettingsDep, data: DataDep
) -> FabsActionOut:
    path = _path(settings, save_id)
    return _act(path, data, UpgradeFab(_founder_id(_state(path)), facility_id))


@router.post(
    "/fabs/{facility_id}/staff",
    response_model=FabsActionOut,
    responses=ERRORS,
    operation_id="staffFab",
)
def staff_fab(
    save_id: str, facility_id: int, body: StaffFabIn, settings: SettingsDep, data: DataDep
) -> FabsActionOut:
    path = _path(settings, save_id)
    return _act(path, data, StaffFacility(_founder_id(_state(path)), facility_id, body.unit_id))


@router.post(
    "/fabs/{facility_id}/sell",
    response_model=FabsActionOut,
    responses=ERRORS,
    operation_id="sellFab",
)
def sell_fab(save_id: str, facility_id: int, settings: SettingsDep, data: DataDep) -> FabsActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SellFacility(_founder_id(_state(path)), facility_id))


@router.post(
    "/fabs/foundry-contract",
    response_model=FabsActionOut,
    responses=ERRORS,
    operation_id="signFoundryContract",
)
def sign_foundry_contract(
    save_id: str, body: FoundryContractIn, settings: SettingsDep, data: DataDep
) -> FabsActionOut:
    """M23a: a multi-month foundry contract with a rival designer (price and volume; the
    designer takes what the fab delivers, before spot slots)."""
    path = _path(settings, save_id)
    actor = _founder_id(_state(path))
    action = SignFoundryContract(
        actor, body.fab_id, body.customer, body.monthly_starts, body.months, body.price_cents
    )
    return _act(path, data, action)
