"""FastAPI app. Thin: routers load a save, call the repository/sim, and return schemas."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from tst.api.routers import (
    coo,
    events,
    facilities,
    finance,
    founder,
    game,
    geo,
    group,
    hardware,
    history,
    holiday,
    meta,
    mna,
    modes,
    org,
    press,
    products,
    public,
    research,
    rivals,
    saves,
    scaleup,
)
from tst.api.schemas.common import ErrorOut
from tst.db.repository import BUSY_MESSAGE, is_locked_error
from tst.db.saves import IronmanSaveError
from tst.sim.errors import (
    CriticalEventOpenError,
    EventError,
    EventsOpenError,
    GameOverError,
    InterviewRequired,
    NotFoundError,
    SaveBusyError,
    SaveExistsError,
    SaveNotFoundError,
    SimError,
    UpgradeNeededError,
)

ERROR_STATUS: dict[type[SimError], int] = {
    SaveNotFoundError: status.HTTP_404_NOT_FOUND,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    SaveExistsError: status.HTTP_409_CONFLICT,
    InterviewRequired: status.HTTP_409_CONFLICT,  # ADR-0016
    GameOverError: status.HTTP_409_CONFLICT,  # ADR-0018
    SaveBusyError: status.HTTP_409_CONFLICT,  # M6 sub-task 0
    CriticalEventOpenError: status.HTTP_409_CONFLICT,  # M6: answer it first (ADR-0006)
    EventsOpenError: status.HTTP_409_CONFLICT,  # M10b: answer major events first (23.1)
    EventError: status.HTTP_409_CONFLICT,
    UpgradeNeededError: status.HTTP_409_CONFLICT,
    IronmanSaveError: status.HTTP_409_CONFLICT,  # M7b: no duplicate or restore
}


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    # Busy is only ever raised before a write commits (M8r): safe to send again.
    retryable = True if code == SaveBusyError.code else None
    return JSONResponse(
        status_code=status_code,
        content=ErrorOut(code=code, message=message, retryable=retryable).model_dump(
            exclude_none=True
        ),
    )


def create_app() -> FastAPI:
    app = FastAPI(title="Tech Startup Tycoon", version="0.0.0")
    app.include_router(saves.router)
    app.include_router(game.router)
    app.include_router(org.router)
    app.include_router(products.router)
    app.include_router(finance.router)
    app.include_router(rivals.router)
    app.include_router(events.router)
    app.include_router(holiday.router)
    app.include_router(history.router)
    app.include_router(coo.router)
    app.include_router(scaleup.router)
    app.include_router(geo.router)  # M9
    app.include_router(facilities.router)  # M12a
    app.include_router(hardware.router)  # M12b
    app.include_router(research.router)  # M11
    app.include_router(public.router)  # M13
    app.include_router(mna.router)  # M14
    app.include_router(press.router)  # M14b
    app.include_router(modes.router)  # M15b
    app.include_router(founder.router)  # M24
    app.include_router(group.router)  # M16
    app.include_router(events.settings_router)
    app.include_router(meta.router)

    @app.exception_handler(SimError)
    async def _sim_error(_request: Request, exc: SimError) -> JSONResponse:
        status_code = next(
            (code for cls, code in ERROR_STATUS.items() if isinstance(exc, cls)),
            status.HTTP_400_BAD_REQUEST,
        )
        if isinstance(exc, EventsOpenError):
            body = ErrorOut(
                code=exc.code,
                message=exc.message,
                event_ids=list(exc.event_ids),
                proposal_ids=list(exc.proposal_ids),
                pitch_ids=list(exc.pitch_ids),
            )
            return JSONResponse(status_code=status_code, content=body.model_dump())
        if isinstance(exc, CriticalEventOpenError):
            body = ErrorOut(code=exc.code, message=exc.message, event_id=exc.event_id)
            return JSONResponse(status_code=status_code, content=body.model_dump())
        return _error(status_code, exc.code, exc.message)

    @app.exception_handler(OperationalError)
    async def _locked(_request: Request, exc: OperationalError) -> JSONResponse:
        """Another process holds the save's write lock: busy, not a server error."""
        if is_locked_error(exc):
            return _error(status.HTTP_409_CONFLICT, SaveBusyError.code, BUSY_MESSAGE)
        raise exc

    @app.exception_handler(RequestValidationError)
    async def _invalid(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_request", details)

    return app


app = create_app()
