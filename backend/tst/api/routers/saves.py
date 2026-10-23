"""Save-scoped routes. Each request opens the save file it names (ADR-0009)."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, status

from tst.api.deps import DataDep, SettingsDep
from tst.api.schemas.common import ErrorOut
from tst.api.schemas.saves import CreateSaveIn, OverviewOut, SaveOut, SnapshotPointOut
from tst.db import repository
from tst.sim.calendar import format_turn
from tst.sim.setup import DEFAULT_FOUNDER

router = APIRouter(prefix="/api/saves", tags=["saves"])

HISTORY_TURNS = 12  # Overview chart window
SEED_BITS = 63  # fits SQLite's signed 64-bit INTEGER

ERRORS: dict[int | str, dict[str, object]] = {
    400: {"model": ErrorOut},
    404: {"model": ErrorOut},
    409: {"model": ErrorOut},
    422: {"model": ErrorOut},
}


def _save_out(summary: repository.SaveSummary) -> SaveOut:
    return SaveOut(
        save_id=summary.slug,
        company_name=summary.company_name,
        scenario_id=summary.scenario_id,
        difficulty=summary.difficulty,
        turn=summary.current_turn,
        date_label=format_turn(summary.current_turn),
    )


def _overview(save_id: str, settings: SettingsDep) -> OverviewOut:
    path = repository.existing_save_path(settings.resolved_save_dir(), save_id)
    with repository.open_session(path) as session:
        ov = repository.player_overview(session, history=HISTORY_TURNS)
    return OverviewOut(
        save_id=save_id,
        company_name=ov.company_name,
        turn=ov.turn,
        date_label=ov.date_label,
        cash_cents=ov.cash_cents,
        monthly_burn_cents=ov.monthly_burn_cents,
        runway_months=ov.runway_months,
        history=[
            SnapshotPointOut(
                turn=turn,
                date_label=format_turn(turn),
                cash_cents=snap.cash_cents,
                monthly_burn_cents=snap.monthly_burn_cents,
            )
            for turn, snap in ov.history
        ],
    )


@router.get("", response_model=list[SaveOut], operation_id="listSaves")
def list_saves(settings: SettingsDep) -> list[SaveOut]:
    return [_save_out(s) for s in repository.list_saves(settings.resolved_save_dir())]


@router.post(
    "",
    response_model=SaveOut,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    operation_id="createSave",
)
def create_save(body: CreateSaveIn, settings: SettingsDep, data: DataDep) -> SaveOut:
    # The sim never generates seeds; the API does when the player leaves it blank.
    seed = body.seed if body.seed is not None else secrets.randbits(SEED_BITS)
    path = repository.create_save(
        body.name,
        seed,
        body.scenario,
        company_name=body.company_name,
        difficulty=body.difficulty,
        founder=body.founder.to_spec() if body.founder else DEFAULT_FOUNDER,
        data=data,
        save_dir=settings.resolved_save_dir(),
    )
    return _save_out(repository.summarize(path))


@router.get("/{save_id}", response_model=SaveOut, responses=ERRORS, operation_id="getSave")
def get_save(save_id: str, settings: SettingsDep) -> SaveOut:
    path = repository.existing_save_path(settings.resolved_save_dir(), save_id)
    return _save_out(repository.summarize(path))


@router.get(
    "/{save_id}/overview",
    response_model=OverviewOut,
    responses=ERRORS,
    operation_id="getOverview",
)
def get_overview(save_id: str, settings: SettingsDep) -> OverviewOut:
    return _overview(save_id, settings)


@router.post(
    "/{save_id}/advance",
    response_model=OverviewOut,
    responses=ERRORS,
    operation_id="advanceTurn",
)
def advance(save_id: str, settings: SettingsDep, data: DataDep) -> OverviewOut:
    path = repository.existing_save_path(settings.resolved_save_dir(), save_id)
    repository.run_turn(path, data)
    return _overview(save_id, settings)
