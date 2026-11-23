"""The desktop build's routes (M58). Not game routes: no save is read or written here, apart
from copying save files for the first-run import and the pre-update backup.

`/api/health` answers everywhere. The `/api/desktop` routes answer `desktop: false` (GET) or
409 `not_desktop` outside the installed game. `POST /api/desktop/focus` (a second launch
bringing this window forward) takes the instance token and is left out of the schema.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from tst.api.schemas.common import ErrorOut
from tst.api.schemas.desktop import (
    ApiKeyIn,
    DesktopOut,
    HealthOut,
    ImportIn,
    ImportOfferOut,
    ImportOut,
    UpdateOut,
)
from tst.desktop import context as desktop_context
from tst.desktop.context import DesktopContext
from tst.desktop.instance import TOKEN_HEADER
from tst.desktop.secrets import clean_key
from tst.desktop.update import UpdateError
from tst.desktop.version import current_version

router = APIRouter(prefix="/api", tags=["desktop"])

ERRORS: dict[int | str, dict[str, object]] = {409: {"model": ErrorOut}, 422: {"model": ErrorOut}}
UPDATING_MESSAGE = "The game is updating; it will restart in a moment."


def _refuse(code: str, message: str, status_code: int = status.HTTP_409_CONFLICT) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorOut(code=code, message=message).model_dump(exclude_none=True),
    )


def _not_desktop() -> JSONResponse:
    return _refuse("not_desktop", "only the installed game has this")


def _out(ctx: DesktopContext | None) -> DesktopOut:
    if ctx is None:
        return DesktopOut(desktop=False, version=current_version())
    offer, release = ctx.import_offer, ctx.release
    return DesktopOut(
        desktop=True,
        version=ctx.version,
        saves_dir=str(ctx.paths.saves),
        key_saved=ctx.key_saved(),
        import_offer=(
            ImportOfferOut(folder=str(offer.folder), saves=list(offer.saves)) if offer else None
        ),
        update_state=ctx.update_state,
        update=(
            UpdateOut(
                version=release.version,
                notes=release.notes,
                page_url=release.page_url,
                size_bytes=release.installer_size,
            )
            if release
            else None
        ),
        update_message=ctx.update_message,
        backup_folder=str(ctx.backup_folder) if ctx.backup_folder else None,
    )


@router.get("/health", response_model=HealthOut, operation_id="getHealth")
def get_health() -> HealthOut:
    """The server is up (the release smoke test and the window wait on this)."""
    ctx = desktop_context.current()
    return HealthOut(version=ctx.version if ctx else current_version())


@router.get("/desktop", response_model=DesktopOut, operation_id="getDesktop")
def get_desktop() -> DesktopOut:
    """The installed game's state: the version, the update offered, the first-run import."""
    return _out(desktop_context.current())


@router.put(
    "/desktop/api-key", response_model=DesktopOut, responses=ERRORS, operation_id="setApiKey"
)
def set_api_key(body: ApiKeyIn) -> DesktopOut | JSONResponse:
    """Store the Anthropic API key in app data (empty removes it). The key is never returned."""
    ctx = desktop_context.current()
    if ctx is None:
        return _not_desktop()
    try:
        key = clean_key(body.key) if body.key.strip() else None
    except ValueError as e:
        return _refuse("invalid_key", str(e), status.HTTP_422_UNPROCESSABLE_CONTENT)
    ctx.save_key(key)
    return _out(ctx)


@router.post(
    "/desktop/import", response_model=ImportOut, responses=ERRORS, operation_id="answerImport"
)
def answer_import(body: ImportIn) -> ImportOut | JSONResponse:
    """The first-run offer: copy the repository's saves, or never ask again."""
    ctx = desktop_context.current()
    if ctx is None:
        return _not_desktop()
    if not body.accept:
        ctx.skip_import()
        return ImportOut(imported=[])
    return ImportOut(imported=ctx.import_saves())


@router.post(
    "/desktop/update", response_model=DesktopOut, responses=ERRORS, operation_id="startUpdate"
)
def start_update() -> DesktopOut | JSONResponse:
    """Update now: download and verify the installer, back up the saves, install, restart."""
    ctx = desktop_context.current()
    if ctx is None:
        return _not_desktop()
    try:
        ctx.begin_update()
    except UpdateError as e:
        return _refuse("update_refused", str(e))
    return _out(ctx)


@router.post(
    "/desktop/update/later", response_model=DesktopOut, responses=ERRORS, operation_id="updateLater"
)
def update_later() -> DesktopOut | JSONResponse:
    """Later: the offer comes back at the next start."""
    ctx = desktop_context.current()
    if ctx is None:
        return _not_desktop()
    ctx.later()
    return _out(ctx)


@router.post("/desktop/focus", include_in_schema=False, status_code=status.HTTP_204_NO_CONTENT)
def focus(token: str | None = Header(default=None, alias=TOKEN_HEADER)) -> Response:
    ctx = desktop_context.current()
    if ctx is None or not ctx.check_token(token):
        return Response(status_code=status.HTTP_403_FORBIDDEN)
    ctx.focus()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def update_guard(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Once the pre-update backup has started, refuse every write but the desktop routes'
    (the backup must be the saves' last state)."""
    ctx = desktop_context.current()
    path = request.url.path
    if (
        ctx is not None
        and ctx.updating
        and request.method not in ("GET", "HEAD", "OPTIONS")
        and path.startswith("/api/")
        and not path.startswith("/api/desktop")
    ):
        return _refuse("save_busy", UPDATING_MESSAGE)
    return await call_next(request)
