"""Save-scoped press routes (M14b, formulas.md 29): press moments, promises and credibility;
rival CEOs and feuds; Replace. Actions run through `repository.run_action` with the founder
as actor (ADR-0014)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import press_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.press import (
    FeudOut,
    PressActionOut,
    PressOut,
    PromiseIn,
    ReplaceableOut,
    ReplaceIn,
    RivalLeaderOut,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import MakePromise, ReplaceLeaver
from tst.sim.errors import UnknownPersonError

router = APIRouter(prefix="/api/saves/{save_id}", tags=["press"])


def _press_act(path: Path, data: LoadedData, action: MakePromise | ReplaceLeaver) -> PressActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return PressActionOut(
        press=press_views.press_out(state, data),
        energy=views.energy(state, data),
        unread_inbox=unread,
    )


@router.get("/press", response_model=PressOut, responses=ERRORS, operation_id="getPress")
def get_press(save_id: str, settings: SettingsDep, data: DataDep) -> PressOut:
    """Credibility, promises and recent press moments, and the promise form (29.6)."""
    return press_views.press_out(_state(_path(settings, save_id)), data)


@router.post(
    "/press/promises", response_model=PressActionOut, responses=ERRORS, operation_id="makePromise"
)
def make_promise(
    save_id: str, body: PromiseIn, settings: SettingsDep, data: DataDep
) -> PressActionOut:
    """A public promise in this month's answered press moment (29.2)."""
    path = _path(settings, save_id)
    action = MakePromise(
        _founder_id(_state(path)),
        body.promise,
        body.product_id,
        body.rival_product_id,
        body.domain,
        body.level,
        body.months,
    )
    return _press_act(path, data, action)


@router.get("/feuds", response_model=list[FeudOut], responses=ERRORS, operation_id="listFeuds")
def list_feuds(save_id: str, settings: SettingsDep, data: DataDep) -> list[FeudOut]:
    state = _state(_path(settings, save_id))
    ids = sorted({f.rival_id for f in state.feuds if f.company_id == state.player.id})
    return sorted((press_views.feud_out(state, rid, data) for rid in ids), key=lambda f: -f.score)


@router.get(
    "/rivals/{rival_id}/leader",
    response_model=RivalLeaderOut,
    responses=ERRORS,
    operation_id="getRivalLeader",
)
def get_rival_leader(
    save_id: str, rival_id: int, settings: SettingsDep, data: DataDep
) -> RivalLeaderOut:
    """The rival's CEO, statements and feud (29.4)."""
    state = _state(_path(settings, save_id))
    if not any(c.id == rival_id and c.is_rival for c in state.companies):
        raise UnknownPersonError(f"no rival {rival_id}")
    return press_views.rival_leader_out(state, rival_id, data)


@router.get(
    "/recruitment/replaceable",
    response_model=list[ReplaceableOut],
    responses=ERRORS,
    operation_id="listReplaceable",
)
def list_replaceable(save_id: str, settings: SettingsDep, data: DataDep) -> list[ReplaceableOut]:
    """Resignations and poaches Replace can fill (29.5)."""
    return press_views.replaceable_out(_state(_path(settings, save_id)), data)


@router.post(
    "/recruitment/replace",
    response_model=PressActionOut,
    responses=ERRORS,
    operation_id="replaceLeaver",
)
def replace_leaver(
    save_id: str, body: ReplaceIn, settings: SettingsDep, data: DataDep
) -> PressActionOut:
    """Replace with a recruiter (29.5)."""
    path = _path(settings, save_id)
    return _press_act(path, data, ReplaceLeaver(_founder_id(_state(path)), body.person_id))
