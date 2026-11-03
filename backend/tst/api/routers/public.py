"""Save-scoped public-company routes (M13, formulas.md 25): the IPO flow, the Stock tab and
the CEO seat. Actions run through `repository.run_action` with the founder (as Chair) as actor
(ADR-0014)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import select

from tst.api import public_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.public import (
    AppointCeoIn,
    BuybackIn,
    CeoAuthorityIn,
    DividendIn,
    GuidanceIn,
    HireBanksIn,
    PublicActionOut,
    PublicOut,
    SecondaryIn,
)
from tst.db import inbox, repository
from tst.db.models import ShareMonthRow
from tst.db.state_io import has_table
from tst.loader import LoadedData
from tst.sim.actions import (
    Action,
    AppointCeo,
    Buyback,
    DeclareDividend,
    DismissCeo,
    HireBanks,
    OverrideCeo,
    SecondaryOffering,
    SetCeoAuthority,
    SetGuidance,
)
from tst.sim.markets_public.models import ShareMonth
from tst.sim.state import GameState

router = APIRouter(prefix="/api/saves/{save_id}", tags=["public"])


def _months(path: Path, state: GameState) -> list[ShareMonth]:
    """Every month end since listing (the state keeps only the last few years)."""
    with repository.open_session(path) as session:
        if not has_table(session, ShareMonthRow):
            return list(state.share_months)
        rows = session.scalars(
            select(ShareMonthRow).where(ShareMonthRow.company_id == state.player.id)
        )
        stored = {
            r.turn: ShareMonth(r.company_id, r.turn, r.price_cents, r.shares, r.mark) for r in rows
        }
    for m in state.share_months:
        if m.company_id == state.player.id:
            stored[m.turn] = m
    return [stored[t] for t in sorted(stored)]


def _out(path: Path, state: GameState, data: LoadedData) -> PublicOut:
    return public_views.public_out(state, _months(path, state), data)


def _act(path: Path, data: LoadedData, action: Action) -> PublicActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return PublicActionOut(
        public=_out(path, state, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get("/public", response_model=PublicOut, responses=ERRORS, operation_id="getPublic")
def get_public(save_id: str, settings: SettingsDep, data: DataDep) -> PublicOut:
    """The IPO flow, the Stock tab and the CEO seat (25.8)."""
    path = _path(settings, save_id)
    return _out(path, _state(path), data)


@router.post(
    "/public/banks", response_model=PublicActionOut, responses=ERRORS, operation_id="hireBanks"
)
def hire_banks(
    save_id: str, body: HireBanksIn, settings: SettingsDep, data: DataDep
) -> PublicActionOut:
    """25.2 step 1: hire the lead underwriter (energy ipo.hire_energy)."""
    path = _path(settings, save_id)
    return _act(path, data, HireBanks(_founder_id(_state(path)), body.bank))


@router.post(
    "/public/guidance", response_model=PublicActionOut, responses=ERRORS, operation_id="setGuidance"
)
def set_guidance(
    save_id: str, body: GuidanceIn, settings: SettingsDep, data: DataDep
) -> PublicActionOut:
    path = _path(settings, save_id)
    action = SetGuidance(_founder_id(_state(path)), body.revenue_cents, body.margin_bp)
    return _act(path, data, action)


@router.post(
    "/public/buyback", response_model=PublicActionOut, responses=ERRORS, operation_id="buyback"
)
def buyback(save_id: str, body: BuybackIn, settings: SettingsDep, data: DataDep) -> PublicActionOut:
    path = _path(settings, save_id)
    return _act(path, data, Buyback(_founder_id(_state(path)), body.amount_cents))


@router.post(
    "/public/dividend",
    response_model=PublicActionOut,
    responses=ERRORS,
    operation_id="declareDividend",
)
def declare_dividend(
    save_id: str, body: DividendIn, settings: SettingsDep, data: DataDep
) -> PublicActionOut:
    path = _path(settings, save_id)
    return _act(path, data, DeclareDividend(_founder_id(_state(path)), body.per_share_cents))


@router.post(
    "/public/secondary",
    response_model=PublicActionOut,
    responses=ERRORS,
    operation_id="secondaryOffering",
)
def secondary_offering(
    save_id: str, body: SecondaryIn, settings: SettingsDep, data: DataDep
) -> PublicActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SecondaryOffering(_founder_id(_state(path)), body.shares))


@router.post(
    "/public/ceo", response_model=PublicActionOut, responses=ERRORS, operation_id="appointCeo"
)
def appoint_ceo(
    save_id: str, body: AppointCeoIn, settings: SettingsDep, data: DataDep
) -> PublicActionOut:
    path = _path(settings, save_id)
    return _act(path, data, AppointCeo(_founder_id(_state(path)), body.person_id))


@router.post(
    "/public/ceo/dismiss",
    response_model=PublicActionOut,
    responses=ERRORS,
    operation_id="dismissCeo",
)
def dismiss_ceo(save_id: str, settings: SettingsDep, data: DataDep) -> PublicActionOut:
    path = _path(settings, save_id)
    return _act(path, data, DismissCeo(_founder_id(_state(path))))


@router.put(
    "/public/ceo/authority",
    response_model=PublicActionOut,
    responses=ERRORS,
    operation_id="setCeoAuthority",
)
def set_ceo_authority(
    save_id: str, body: CeoAuthorityIn, settings: SettingsDep, data: DataDep
) -> PublicActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SetCeoAuthority(_founder_id(_state(path)), tuple(body.scopes)))


@router.post(
    "/public/ceo/decisions/{decision_id}/override",
    response_model=PublicActionOut,
    responses=ERRORS,
    operation_id="overrideCeo",
)
def override_ceo(
    save_id: str, decision_id: int, settings: SettingsDep, data: DataDep
) -> PublicActionOut:
    """25.6: reverse one CEO decision (energy ceo.override_energy)."""
    path = _path(settings, save_id)
    return _act(path, data, OverrideCeo(_founder_id(_state(path)), decision_id))
