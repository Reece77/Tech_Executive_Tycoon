"""Rivals, market news and approaches (M5, docs/formulas.md 15.5-15.6). Read-only: the
counter to an approach is the raise action (org routes), and its preview here shows only
the new band."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from tst.api import rival_views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _path
from tst.api.routers.saves import ERRORS
from tst.api.schemas.rivals import (
    ApproachOut,
    CounterIn,
    CounterPreviewOut,
    NewsOut,
    RivalProfileOut,
    RivalsOut,
)
from tst.db import repository
from tst.sim.errors import NotFoundError

router = APIRouter(prefix="/api/saves/{save_id}", tags=["rivals"])


class UnknownRivalError(NotFoundError):
    code = "unknown_rival"


class UnknownApproachError(NotFoundError):
    code = "unknown_approach"


@router.get("/rivals", response_model=RivalsOut, responses=ERRORS, operation_id="listRivals")
def list_rivals(
    save_id: str,
    settings: SettingsDep,
    data: DataDep,
    view: Annotated[str, Query(pattern="^(all|markets|startups)$")] = "all",
) -> RivalsOut:
    """Every rival: in your markets, all, or startups (15.5)."""
    with repository.open_session(_path(settings, save_id)) as session:
        state = repository.load_state(session)
        balances = repository.ledger_balances(session, state.turn)
    return rival_views.rivals_out(state, balances, data, list(state.rival_moves), view)


@router.get(
    "/rivals/{company_id}",
    response_model=RivalProfileOut,
    responses=ERRORS,
    operation_id="getRival",
)
def get_rival(
    save_id: str, company_id: int, settings: SettingsDep, data: DataDep
) -> RivalProfileOut:
    with repository.open_session(_path(settings, save_id)) as session:
        state = repository.load_state(session)
        balances = repository.ledger_balances(session, state.turn)
    company = next((c for c in state.companies if c.id == company_id and not c.is_player), None)
    if company is None:
        raise UnknownRivalError(f"no rival {company_id}")
    return rival_views.rival_profile(state, company, balances, data, list(state.rival_moves))


@router.get("/news", response_model=NewsOut, responses=ERRORS, operation_id="getMarketNews")
def market_news(save_id: str, settings: SettingsDep) -> NewsOut:
    """Rival moves and startup events of the last 24 months, newest month first (15.5)."""
    with repository.open_session(_path(settings, save_id)) as session:
        state = repository.load_state(session)
    return NewsOut(months=rival_views.news_months(list(state.rival_moves)))


@router.get(
    "/approaches",
    response_model=list[ApproachOut],
    responses=ERRORS,
    operation_id="listApproaches",
)
def list_approaches(save_id: str, settings: SettingsDep, data: DataDep) -> list[ApproachOut]:
    """Rivals' open offers to your people, answered at Continue (15.6)."""
    with repository.open_session(_path(settings, save_id)) as session:
        state = repository.load_state(session)
    return [
        rival_views.approach_out(state, a, data)
        for a in state.approaches
        if a.status == "pending" and state.employment_of(a.person_id) is not None
    ]


@router.post(
    "/approaches/{approach_id}/counter-preview",
    response_model=CounterPreviewOut,
    responses=ERRORS,
    operation_id="previewCounter",
)
def preview_counter(
    save_id: str, approach_id: int, body: CounterIn, settings: SettingsDep, data: DataDep
) -> CounterPreviewOut:
    """The band now and after a raise to `salary_cents`. Nothing is saved."""
    with repository.open_session(_path(settings, save_id)) as session:
        state = repository.load_state(session)
    approach = next((a for a in state.approaches if a.id == approach_id), None)
    if approach is None or approach.status != "pending":
        raise UnknownApproachError(f"no open approach {approach_id}")
    return CounterPreviewOut(
        band_now=rival_views.band(state, approach, data),
        band_after=rival_views.band(state, approach, data, salary=body.salary_cents),
    )
