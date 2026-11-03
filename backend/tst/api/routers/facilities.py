"""Save-scoped Infrastructure routes (M12a, formulas.md 22): data centres, component indexes,
contracts and Cloud hosting. Actions run through `repository.run_action` with the founder as
actor (ADR-0014)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from tst.api import facility_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.facilities import (
    BuildIn,
    BuildPreviewOut,
    ContractIn,
    InfrastructureActionOut,
    InfrastructureOut,
    StaffIn,
)
from tst.db import inbox, repository
from tst.db.models import SupplyMonthRow
from tst.db.state_io import good_month_from_row, has_table
from tst.loader import LoadedData
from tst.sim.actions import (
    Action,
    BuildFacility,
    SellCapacity,
    SellFacility,
    SignContract,
    StaffFacility,
)
from tst.sim.facilities import compute
from tst.sim.state import GameState

router = APIRouter(prefix="/api/saves/{save_id}", tags=["facilities"])


def _stored(path: Path, state: GameState, data: LoadedData) -> facility_views.Stored:
    """Goods' months already played after the history (the API never computes ahead)."""
    components = data.game_data.components
    if components is None or state.turn <= components.last_turn:
        return {}
    since = state.turn - data.balance.supply.history_months - 1
    with repository.open_session(path) as session:
        if not has_table(session, SupplyMonthRow):
            return {}
        rows = session.scalars(select(SupplyMonthRow).where(SupplyMonthRow.turn >= since))
        return {(r.good, r.turn): good_month_from_row(r) for r in rows}


def _out(path: Path, state: GameState, data: LoadedData) -> InfrastructureOut:
    return facility_views.infrastructure_out(state, data, _stored(path, state, data))


def _act(path: Path, data: LoadedData, action: Action) -> InfrastructureActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return InfrastructureActionOut(
        infrastructure=_out(path, state, data),
        energy=views.energy(state, data),
        unread_inbox=unread,
    )


@router.get(
    "/infrastructure",
    response_model=InfrastructureOut,
    responses=ERRORS,
    operation_id="getInfrastructure",
)
def get_infrastructure(save_id: str, settings: SettingsDep, data: DataDep) -> InfrastructureOut:
    """The Infrastructure screen: component indexes, data centres, contracts and Cloud
    hosting (22.6)."""
    path = _path(settings, save_id)
    return _out(path, _state(path), data)


@router.get(
    "/infrastructure/build-preview",
    response_model=BuildPreviewOut,
    responses=ERRORS,
    operation_id="previewBuild",
)
def preview_build(
    save_id: str,
    settings: SettingsDep,
    data: DataDep,
    kind: Annotated[str | None, Query(description="Default: the first kind")] = None,
    region: Annotated[str | None, Query(description="Default: the home region")] = None,
    units: Annotated[int | None, Query(description="Default: the smallest size")] = None,
    contract_id: Annotated[int | None, Query()] = None,
) -> BuildPreviewOut:
    """Capex, build time, shortage delay and staff for a build (the Build dialog)."""
    path = _path(settings, save_id)
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        balances = repository.current_balances(session, state.turn)
    kind = kind or next(iter(data.balance.facility.kinds))
    region = region or compute.home_region_of(state, data.balance, data.game_data)
    units = units or data.balance.facility.sizes[0]
    b = data.balance
    if kind not in b.facility.kinds or b.facility.kinds[kind].output_good not in b.compute.goods:
        from tst.sim.errors import FacilityRuleError

        # Infrastructure previews data centres only; plants are built from Hardware (M12b)
        raise FacilityRuleError(f"{kind!r} is not a data-centre kind")
    return facility_views.build_preview(state, kind, region, units, contract_id, balances, data)


@router.post(
    "/infrastructure/facilities",
    response_model=InfrastructureActionOut,
    responses=ERRORS,
    operation_id="buildFacility",
)
def build_facility(
    save_id: str, body: BuildIn, settings: SettingsDep, data: DataDep
) -> InfrastructureActionOut:
    path = _path(settings, save_id)
    action = BuildFacility(
        _founder_id(_state(path)), body.kind, body.region, body.units, body.contract_id
    )
    return _act(path, data, action)


@router.post(
    "/infrastructure/facilities/{facility_id}/sell",
    response_model=InfrastructureActionOut,
    responses=ERRORS,
    operation_id="sellFacility",
)
def sell_facility(
    save_id: str, facility_id: int, settings: SettingsDep, data: DataDep
) -> InfrastructureActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SellFacility(_founder_id(_state(path)), facility_id))


@router.post(
    "/infrastructure/facilities/{facility_id}/staff",
    response_model=InfrastructureActionOut,
    responses=ERRORS,
    operation_id="staffFacility",
)
def staff_facility(
    save_id: str, facility_id: int, body: StaffIn, settings: SettingsDep, data: DataDep
) -> InfrastructureActionOut:
    path = _path(settings, save_id)
    return _act(path, data, StaffFacility(_founder_id(_state(path)), facility_id, body.unit_id))


@router.post(
    "/infrastructure/contracts",
    response_model=InfrastructureActionOut,
    responses=ERRORS,
    operation_id="signContract",
)
def sign_contract(
    save_id: str, body: ContractIn, settings: SettingsDep, data: DataDep
) -> InfrastructureActionOut:
    path = _path(settings, save_id)
    action = SignContract(_founder_id(_state(path)), body.good, body.months, body.volume)
    return _act(path, data, action)


@router.post(
    "/infrastructure/cloud",
    response_model=InfrastructureActionOut,
    responses=ERRORS,
    operation_id="sellCapacity",
)
def sell_capacity(save_id: str, settings: SettingsDep, data: DataDep) -> InfrastructureActionOut:
    """Start selling spare capacity as Cloud hosting (22.3)."""
    path = _path(settings, save_id)
    return _act(path, data, SellCapacity(_founder_id(_state(path))))
