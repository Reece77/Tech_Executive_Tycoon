"""The living world (M28, docs/formulas.md 41.7): World news with filters and the chain
companies by good. Read-only; a company's page is the Rival screen's (`getRival`)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from tst.api import world_views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _path
from tst.api.routers.saves import ERRORS
from tst.api.schemas.world import ChainOut, WorldNewsOut
from tst.db import repository

router = APIRouter(prefix="/api/saves/{save_id}", tags=["world"])


@router.get(
    "/world-news", response_model=WorldNewsOut, responses=ERRORS, operation_id="getWorldNews"
)
def world_news(
    save_id: str,
    settings: SettingsDep,
    data: DataDep,
    company: Annotated[int | None, Query(ge=1)] = None,
    region: Annotated[str | None, Query(max_length=64)] = None,
    good: Annotated[str | None, Query(max_length=64)] = None,
    kind: Annotated[str | None, Query(max_length=32)] = None,
) -> WorldNewsOut:
    """Rivals' deals, capacity moves, mothballings, executive moves and regional cycles, newest
    first, filtered by company, region, good and kind (41.7)."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
    return world_views.world_news(state, data, company, region, good, kind)


@router.get("/chain", response_model=ChainOut, responses=ERRORS, operation_id="getChain")
def chain(save_id: str, settings: SettingsDep, data: DataDep) -> ChainOut:
    """Chain companies by good: capacity, output and utilisation (41.1)."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
    return world_views.chain(state, data)
