"""The local API answers this computer's own pages only (M57r-B, review 10 item 2).

The API listens on 127.0.0.1, but a web page in the player's browser can still reach it: a
cross-site form or `fetch` sends a POST to `127.0.0.1:<port>` (forcing `/api/desktop/update`),
and DNS rebinding points an attacker's host name at 127.0.0.1 to read and write every route.
This middleware closes both:

- **Host:** every request's `Host` must name a loopback host (`127.0.0.1`, `localhost`,
  `[::1]`, plus `TST_ALLOWED_HOSTS` for test clients). A rebound name never matches. In the
  installed game (a desktop context is installed) the port must also be the server's own.
- **Origin:** a request that is not GET, HEAD or OPTIONS and carries an `Origin` must come
  from such a host too (in the installed game, exactly `http://<its Host>`); `null` and any
  foreign origin are refused. A request with no `Origin` is not from a browser page's script
  or form (browsers send one on every cross-origin write) and passes.

The installed game's own desktop writes also need the instance token (`routers/desktop.py`).
"""

from __future__ import annotations

import urllib.parse

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from tst.api.schemas.common import ErrorOut
from tst.config import get_settings
from tst.desktop import context as desktop_context

LOOPBACK = frozenset({"127.0.0.1", "localhost", "[::1]", "::1"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _refuse(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=ErrorOut(code="foreign_request", message=message).model_dump(exclude_none=True),
    )


def _split(host: str) -> tuple[str, int | None]:
    """'127.0.0.1:8000' -> ('127.0.0.1', 8000); '[::1]:80' -> ('[::1]', 80)."""
    host = host.strip().lower()
    if host.startswith("["):
        end = host.find("]")
        name, rest = host[: end + 1], host[end + 1 :]
    else:
        name, _, rest = host.partition(":")
        rest = ":" + rest if rest else ""
    if rest.startswith(":") and rest[1:].isdigit():
        return name, int(rest[1:])
    return name, None if not rest else -1


def allowed_names() -> frozenset[str]:
    extra = get_settings().allowed_hosts or ""
    return LOOPBACK | {h.strip().lower() for h in extra.split(",") if h.strip()}


def host_ok(host: str, names: frozenset[str], port: int | None) -> bool:
    name, given = _split(host)
    if name not in names or given == -1:
        return False
    return port is None or given == port


def origin_ok(origin: str, host: str, names: frozenset[str], desktop: bool) -> bool:
    parts = urllib.parse.urlsplit(origin.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return False  # "null", file:, data:, extensions
    if desktop:
        return parts.scheme == "http" and parts.netloc.lower() == host.strip().lower()
    return host_ok(parts.netloc, names, None)


async def local_guard(request: Request, call_next: RequestResponseEndpoint) -> Response:
    ctx = desktop_context.current()
    names = allowed_names()
    host = request.headers.get("host", "")
    server = request.scope.get("server")
    port = int(server[1]) if ctx is not None and server and server[1] else None
    if not host_ok(host, names, port):
        return _refuse("this API answers requests for this computer's own address only")
    origin = request.headers.get("origin")
    if (
        origin is not None
        and request.method not in SAFE_METHODS
        and not origin_ok(origin, host, names, ctx is not None)
    ):
        return _refuse("this API accepts changes from the game's own page only")
    return await call_next(request)
