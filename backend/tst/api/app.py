"""FastAPI app. Thin: routers load a save, call the repository/sim, and return schemas."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from tst.api.routers import game, meta, saves
from tst.api.schemas.common import ErrorOut
from tst.sim.errors import (
    InterviewRequired,
    NotFoundError,
    SaveExistsError,
    SaveNotFoundError,
    SimError,
)

ERROR_STATUS: dict[type[SimError], int] = {
    SaveNotFoundError: status.HTTP_404_NOT_FOUND,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    SaveExistsError: status.HTTP_409_CONFLICT,
    InterviewRequired: status.HTTP_409_CONFLICT,  # ADR-0016
}


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=ErrorOut(code=code, message=message).model_dump()
    )


def create_app() -> FastAPI:
    app = FastAPI(title="Tech Startup Tycoon", version="0.0.0")
    app.include_router(saves.router)
    app.include_router(game.router)
    app.include_router(meta.router)

    @app.exception_handler(SimError)
    async def _sim_error(_request: Request, exc: SimError) -> JSONResponse:
        status_code = next(
            (code for cls, code in ERROR_STATUS.items() if isinstance(exc, cls)),
            status.HTTP_400_BAD_REQUEST,
        )
        return _error(status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _invalid(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_request", details)

    return app


app = create_app()
