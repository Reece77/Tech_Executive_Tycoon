"""Save-scoped routes for the family (M36, formulas.md 45): the Family screen, family time,
education, mentoring, a job in the group, succession, gifts, the trust and shares for the
foundation. Actions run through `repository.run_action` with the family head as actor."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import family_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.family import (
    EducateIn,
    FamilyActionOut,
    FamilyJobIn,
    FamilyOut,
    FamilyTimeIn,
    GiftIn,
    MentorIn,
    SharesIn,
    SuccessionIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions.family import (
    EducateChild,
    FamilyAction,
    FundTrust,
    GiftShares,
    GiveSharesToFoundation,
    NameSuccessor,
    OfferFamilyJob,
    RetireAdviser,
    SetFamilyTime,
    SetMentoring,
)
from tst.sim.state import GameState

router = APIRouter(prefix="/api/saves/{save_id}", tags=["family"])


def _out(path: Path, state: GameState, data: LoadedData) -> FamilyOut:
    with repository.read_session(path) as session:
        balances = repository.ledger_balances(session)
    return family_views.family_out(state, balances, data)


def _act(path: Path, data: LoadedData, action: FamilyAction) -> FamilyActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return FamilyActionOut(
        family=_out(path, state, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get("/family", response_model=FamilyOut, responses=ERRORS, operation_id="getFamily")
def get_family(save_id: str, settings: SettingsDep, data: DataDep) -> FamilyOut:
    """Members, ages, relationships, education, ratings as ranges, readiness, family time,
    the adviser, the estate quote and the dynasty score (45.9)."""
    path = _path(settings, save_id)
    return _out(path, _state(path), data)


@router.post(
    "/family/time", response_model=FamilyActionOut, responses=ERRORS, operation_id="setFamilyTime"
)
def set_time(
    save_id: str, body: FamilyTimeIn, settings: SettingsDep, data: DataDep
) -> FamilyActionOut:
    """Energy a month for the family, 0-20 (45.2)."""
    path = _path(settings, save_id)
    return _act(path, data, SetFamilyTime(_founder_id(_state(path)), body.energy))


@router.post(
    "/family/educate", response_model=FamilyActionOut, responses=ERRORS, operation_id="educate"
)
def educate(save_id: str, body: EducateIn, settings: SettingsDep, data: DataDep) -> FamilyActionOut:
    """A school at 12, a university at 18, an MBA from 22, paid from personal cash (45.3)."""
    path = _path(settings, save_id)
    action = EducateChild(
        _founder_id(_state(path)), body.person_id, body.stage, body.tier, body.degree
    )
    return _act(path, data, action)


@router.post(
    "/family/mentor", response_model=FamilyActionOut, responses=ERRORS, operation_id="setMentoring"
)
def mentor(save_id: str, body: MentorIn, settings: SettingsDep, data: DataDep) -> FamilyActionOut:
    """Mentor an heir in the group: 3 energy a month (45.4)."""
    path = _path(settings, save_id)
    return _act(path, data, SetMentoring(_founder_id(_state(path)), body.person_id, body.on))


@router.post(
    "/family/job", response_model=FamilyActionOut, responses=ERRORS, operation_id="offerFamilyJob"
)
def job(save_id: str, body: FamilyJobIn, settings: SettingsDep, data: DataDep) -> FamilyActionOut:
    """Offer a grown child a role in a group company (45.4)."""
    path = _path(settings, save_id)
    action = OfferFamilyJob(
        _founder_id(_state(path)), body.person_id, body.company_id, body.role, body.level
    )
    return _act(path, data, action)


@router.post(
    "/family/succession",
    response_model=FamilyActionOut,
    responses=ERRORS,
    operation_id="nameSuccessor",
)
def name_successor(
    save_id: str, body: SuccessionIn, settings: SettingsDep, data: DataDep
) -> FamilyActionOut:
    """Hand over to an heir (you then play them) or a professional CEO (45.5)."""
    path = _path(settings, save_id)
    action = NameSuccessor(
        _founder_id(_state(path)), body.heir_id, body.ceo_person_id, body.professional
    )
    return _act(path, data, action)


@router.post(
    "/family/gift", response_model=FamilyActionOut, responses=ERRORS, operation_id="giftShares"
)
def gift(save_id: str, body: GiftIn, settings: SettingsDep, data: DataDep) -> FamilyActionOut:
    """Gift shares to a child; gift tax above the lifetime exemption (45.6)."""
    path = _path(settings, save_id)
    return _act(path, data, GiftShares(_founder_id(_state(path)), body.heir_id, body.shares))


@router.post(
    "/family/trust", response_model=FamilyActionOut, responses=ERRORS, operation_id="fundTrust"
)
def trust(save_id: str, body: SharesIn, settings: SettingsDep, data: DataDep) -> FamilyActionOut:
    """Put shares in the family trust, outside the estate (45.6)."""
    path = _path(settings, save_id)
    return _act(path, data, FundTrust(_founder_id(_state(path)), body.shares))


@router.post(
    "/family/foundation-shares",
    response_model=FamilyActionOut,
    responses=ERRORS,
    operation_id="giveSharesToFoundation",
)
def foundation_shares(
    save_id: str, body: SharesIn, settings: SettingsDep, data: DataDep
) -> FamilyActionOut:
    """Give shares to the foundation: they leave the estate and count toward legacy (45.6)."""
    path = _path(settings, save_id)
    return _act(path, data, GiveSharesToFoundation(_founder_id(_state(path)), body.shares))


@router.post(
    "/family/adviser/retire",
    response_model=FamilyActionOut,
    responses=ERRORS,
    operation_id="retireAdviser",
)
def retire_adviser(save_id: str, settings: SettingsDep, data: DataDep) -> FamilyActionOut:
    """The adviser leaves the board (45.5)."""
    path = _path(settings, save_id)
    return _act(path, data, RetireAdviser(_founder_id(_state(path))))
