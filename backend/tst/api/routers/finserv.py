"""Save-scoped routes for financial services and currencies (M54, docs/formulas.md 64): the Bank,
Payments, Insurance and Currency screens (one view) and the founder's finance and currency actions.
Banking, payments and insurance lines are created, priced and launched through the product
routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import finserv_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.finserv import (
    AmountIn,
    BankSettingsIn,
    FinservActionOut,
    FinservScreenOut,
    ForwardIn,
    ProgrammeIn,
    RegionIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.finserv.actions import (
    ApplyCharter,
    ApplyInsuranceLicence,
    BankCapital,
    InsurerCapital,
    LaunchNetwork,
    PartnerBank,
    SetBank,
)
from tst.sim.fx.actions import BuyForward, SetHedgeProgramme

router = APIRouter(prefix="/api/saves/{save_id}", tags=["finserv"])


def _screen(path: Path, data: LoadedData) -> FinservScreenOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return finserv_views.finserv_out(state, data)


def _act(path: Path, data: LoadedData, action: Action) -> FinservActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return FinservActionOut(
        finserv=_screen(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


def _actor(path: Path) -> int:
    return _founder_id(_state(path))


@router.get(
    "/finserv", response_model=FinservScreenOut, responses=ERRORS, operation_id="getFinserv"
)
def get_finserv(save_id: str, settings: SettingsDep, data: DataDep) -> FinservScreenOut:
    """Banks, payments, the insurer and currency exposure (the four screens)."""
    return _screen(_path(settings, save_id), data)


@router.post(
    "/finserv/charter",
    response_model=FinservActionOut,
    responses=ERRORS,
    operation_id="applyCharter",
)
def apply_charter(
    save_id: str, body: RegionIn, settings: SettingsDep, data: DataDep
) -> FinservActionOut:
    path = _path(settings, save_id)
    return _act(path, data, ApplyCharter(_actor(path), body.region))


@router.post(
    "/finserv/partner",
    response_model=FinservActionOut,
    responses=ERRORS,
    operation_id="partnerBank",
)
def partner_bank(
    save_id: str, body: RegionIn, settings: SettingsDep, data: DataDep
) -> FinservActionOut:
    path = _path(settings, save_id)
    return _act(path, data, PartnerBank(_actor(path), body.region))


@router.post(
    "/finserv/banks/{bank_id}/settings",
    response_model=FinservActionOut,
    responses=ERRORS,
    operation_id="setBank",
)
def set_bank(
    save_id: str, bank_id: int, body: BankSettingsIn, settings: SettingsDep, data: DataDep
) -> FinservActionOut:
    path = _path(settings, save_id)
    action = SetBank(
        _actor(path), bank_id, body.beta, body.loan_to_deposit, body.securities_share, body.duration
    )
    return _act(path, data, action)


@router.post(
    "/finserv/banks/{bank_id}/capital",
    response_model=FinservActionOut,
    responses=ERRORS,
    operation_id="bankCapital",
)
def bank_capital(
    save_id: str, bank_id: int, body: AmountIn, settings: SettingsDep, data: DataDep
) -> FinservActionOut:
    path = _path(settings, save_id)
    return _act(path, data, BankCapital(_actor(path), bank_id, body.amount_cents))


@router.post(
    "/finserv/networks",
    response_model=FinservActionOut,
    responses=ERRORS,
    operation_id="launchNetwork",
)
def launch_network(
    save_id: str, body: RegionIn, settings: SettingsDep, data: DataDep
) -> FinservActionOut:
    path = _path(settings, save_id)
    return _act(path, data, LaunchNetwork(_actor(path), body.region))


@router.post(
    "/finserv/insurance/licence",
    response_model=FinservActionOut,
    responses=ERRORS,
    operation_id="applyInsuranceLicence",
)
def apply_licence(
    save_id: str, body: RegionIn, settings: SettingsDep, data: DataDep
) -> FinservActionOut:
    path = _path(settings, save_id)
    return _act(path, data, ApplyInsuranceLicence(_actor(path), body.region))


@router.post(
    "/finserv/insurance/capital",
    response_model=FinservActionOut,
    responses=ERRORS,
    operation_id="insurerCapital",
)
def insurer_capital(
    save_id: str, body: AmountIn, settings: SettingsDep, data: DataDep
) -> FinservActionOut:
    path = _path(settings, save_id)
    return _act(path, data, InsurerCapital(_actor(path), body.amount_cents))


@router.post(
    "/finserv/forwards",
    response_model=FinservActionOut,
    responses=ERRORS,
    operation_id="buyForward",
)
def buy_forward(
    save_id: str, body: ForwardIn, settings: SettingsDep, data: DataDep
) -> FinservActionOut:
    path = _path(settings, save_id)
    return _act(path, data, BuyForward(_actor(path), body.region, body.notional_cents, body.months))


@router.post(
    "/finserv/programme",
    response_model=FinservActionOut,
    responses=ERRORS,
    operation_id="setHedgeProgramme",
)
def set_programme(
    save_id: str, body: ProgrammeIn, settings: SettingsDep, data: DataDep
) -> FinservActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SetHedgeProgramme(_actor(path), body.share, body.term_months))
