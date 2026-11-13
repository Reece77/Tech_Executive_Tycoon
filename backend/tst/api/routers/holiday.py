"""Holiday routes (docs/formulas.md 17.1; M7b): start a holiday as a background job, follow
it, and ask it to stop after the month in progress."""

from __future__ import annotations

from fastapi import APIRouter, status

from tst import holiday
from tst.api import interruptions
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _path
from tst.api.routers.saves import ERRORS
from tst.api.schemas.holiday import HolidayIn, HolidayOut
from tst.db import repository
from tst.loader import LoadedData
from tst.sim.calendar import format_turn

router = APIRouter(prefix="/api/saves/{save_id}/holiday", tags=["holiday"])


def _out(
    job: holiday.HolidayJob | None, turn: int, data: LoadedData, default_stop: str
) -> HolidayOut:
    keys = data.balance.holiday
    return HolidayOut(
        status=job.status if job else "idle",
        months=job.months if job else 0,
        months_done=job.months_done if job else 0,
        stop=job.stop if job else None,
        turn=turn,
        date_label=format_turn(turn),
        reason=job.reason if job else None,
        reason_text=holiday.REASON_TEXT[job.reason] if job and job.reason else None,
        summary_item_id=job.summary_item_id if job else None,
        error=job.error if job else None,
        stop_requested=job.stop_requested.is_set() if job else False,
        max_months=keys.max_months,
        default_months=keys.default_months,
        default_stop=default_stop,
        stop_runway_months=keys.stop_runway_months,
    )


def _default_stop(settings: SettingsDep, data: LoadedData) -> holiday.StopLevel:
    """M29 (42.4): Interruptions at critical only makes critical the default stop; otherwise
    the balance default."""
    if interruptions.stop_on(settings.resolved_save_dir()) == "critical":
        return "critical"
    return data.balance.holiday.default_stop


def _turn(save_id: str, settings: SettingsDep) -> int:
    with repository.read_session(_path(settings, save_id)) as session:
        return repository.read_state(session).turn


@router.get("", response_model=HolidayOut, responses=ERRORS, operation_id="getHoliday")
def get_holiday(save_id: str, settings: SettingsDep, data: DataDep) -> HolidayOut:
    """The save's holiday: running (months done, the date), or the last one this session."""
    job = holiday.job_for(_path(settings, save_id))
    running = job is not None and job.status == "running"
    return _out(
        job,
        job.turn if job and running else _turn(save_id, settings),
        data,
        _default_stop(settings, data),
    )


@router.post(
    "",
    response_model=HolidayOut,
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERRORS,
    operation_id="startHoliday",
)
def start_holiday(
    save_id: str, body: HolidayIn, settings: SettingsDep, data: DataDep
) -> HolidayOut:
    """Start a holiday: one Continue a month until a stop reason (17.1). 409 if the save is
    busy, the game is over or a critical event is open."""
    keys = data.balance.holiday
    job = holiday.start_job(
        _path(settings, save_id),
        save_id,
        data,
        body.months if body.months is not None else keys.default_months,
        body.stop or _default_stop(settings, data),
    )
    return _out(job, job.turn, data, _default_stop(settings, data))


@router.post("/stop", response_model=HolidayOut, responses=ERRORS, operation_id="stopHoliday")
def stop_holiday(save_id: str, settings: SettingsDep, data: DataDep) -> HolidayOut:
    """Stop after the month in progress; nothing is rolled back."""
    job = holiday.job_for(_path(settings, save_id))
    if job is not None and job.status == "running":
        job.stop_requested.set()
    return _out(
        job, job.turn if job else _turn(save_id, settings), data, _default_stop(settings, data)
    )
