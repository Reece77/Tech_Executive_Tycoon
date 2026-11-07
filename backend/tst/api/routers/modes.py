"""Save-scoped M15b routes (formulas.md 30): rankings, scores and continue-until."""

from __future__ import annotations

from fastapi import APIRouter

from tst.api import modes_views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _path
from tst.api.routers.saves import ERRORS
from tst.api.schemas.modes import RankingsOut
from tst.db import repository

router = APIRouter(prefix="/api/saves/{save_id}", tags=["modes"])


@router.get("/rankings", response_model=RankingsOut, responses=ERRORS, operation_id="getRankings")
def get_rankings(
    save_id: str, settings: SettingsDep, data: DataDep, year: int | None = None
) -> RankingsOut:
    """The industry rankings of `year` (default the latest January's), 30.4."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
    return modes_views.rankings_out(state, year)
