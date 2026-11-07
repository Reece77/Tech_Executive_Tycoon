"""History routes (docs/formulas.md 17.2; M7b): read-only, from stored rows, shown values only."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from tst.api import history_views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _path
from tst.api.routers.saves import ERRORS
from tst.api.schemas.history import (
    ChartsOut,
    HallOfFameOut,
    StorylineHistoryOut,
    TimelineOut,
    VentureOut,
)
from tst.db import repository
from tst.sim.errors import NotFoundError
from tst.sim.state import GameState

router = APIRouter(prefix="/api/saves/{save_id}/history", tags=["history"])


def _company(state: GameState, company_id: int | None) -> int:
    """The company whose history is asked for: the player's (default) or one they sold
    before founding again (M15b addendum 10)."""
    if company_id is None or company_id == state.player.id:
        return state.player.id
    if any(v.company_id == company_id for v in state.ventures):
        return company_id
    raise NotFoundError(f"you never ran company {company_id}")


PAGE = 50  # tunable-exempt: rows per timeline page


@router.get("/timeline", response_model=TimelineOut, responses=ERRORS, operation_id="getTimeline")
def get_timeline(
    save_id: str,
    settings: SettingsDep,
    data: DataDep,
    search: str = "",
    year: int | None = None,
    category: Annotated[
        Literal["people", "products", "finance", "rivals", "events"] | None, Query()
    ] = None,
    source: Annotated[Literal["player", "delegate", "default"] | None, Query()] = None,
    person_id: int | None = None,
    product_id: int | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = PAGE,
    company_id: int | None = None,
) -> TimelineOut:
    """Everything that happened to your company, newest first, with a summary line per
    month. Search matches titles, bodies and names (case-insensitive)."""
    with repository.read_session(_path(settings, save_id)) as session:
        company = _company(repository.read_state(session), company_id)
        return history_views.timeline(
            session,
            company,
            data,
            search=search,
            year=year,
            category=category,
            source=source,
            person_id=person_id,
            product_id=product_id,
            offset=offset,
            limit=limit,
        )


@router.get("/charts", response_model=ChartsOut, responses=ERRORS, operation_id="getHistoryCharts")
def get_charts(save_id: str, settings: SettingsDep, company_id: int | None = None) -> ChartsOut:
    """Every month-end KPI, and each product's MRR and customers, oldest first."""
    with repository.read_session(_path(settings, save_id)) as session:
        company = _company(repository.read_state(session), company_id)
        return history_views.charts(session, company)


@router.get(
    "/storylines",
    response_model=list[StorylineHistoryOut],
    responses=ERRORS,
    operation_id="getHistoryStorylines",
)
def get_storylines(
    save_id: str, settings: SettingsDep, company_id: int | None = None
) -> list[StorylineHistoryOut]:
    """Each storyline with its steps: month, title and the choice taken."""
    with repository.read_session(_path(settings, save_id)) as session:
        company = _company(repository.read_state(session), company_id)
        return history_views.storylines(session, company)


@router.get(
    "/hall-of-fame",
    response_model=HallOfFameOut,
    responses=ERRORS,
    operation_id="getHallOfFame",
)
def get_hall_of_fame(
    save_id: str, settings: SettingsDep, data: DataDep, company_id: int | None = None
) -> HallOfFameOut:
    """Records computed from history when the screen opens; shown values only. A company the
    player sold is judged up to its sale (M15b addendum 10)."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        company = _company(state, company_id)
        venture = next((v for v in state.ventures if v.company_id == company), None)
        turn = venture.ended_turn if venture is not None else state.turn
        return history_views.hall_of_fame(session, company, turn, data)


@router.get(
    "/companies",
    response_model=list[VentureOut],
    responses=ERRORS,
    operation_id="getHistoryCompanies",
)
def get_companies(save_id: str, settings: SettingsDep) -> list[VentureOut]:
    """Every company the player has run, oldest first: History, the score and the Hall of
    Fame show each apart (M15b addendum 10)."""
    with repository.read_session(_path(settings, save_id)) as session:
        return history_views.ventures_out(repository.read_state(session))
