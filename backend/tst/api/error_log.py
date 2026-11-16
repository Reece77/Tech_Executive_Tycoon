"""Server errors written to a file (M35a sub-task 2): with TST_ERROR_LOG set, every request
that ends in an unhandled exception or a 5xx response appends one JSON line (method, path,
status, the exception and the innermost `tst` frame). e2e sets it and fails the run on any
line its allow-list does not name (frontend/e2e/server-errors.ts)."""

from __future__ import annotations

import json
import threading
import traceback
from pathlib import Path
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_LOCK = threading.Lock()


def _where(exc: BaseException) -> str | None:
    """The innermost frame in the game's own code, as `tst/api/x.py:12 in f`, looking through
    the exceptions it was raised from (a sync endpoint's StopIteration arrives as asyncio's
    RuntimeError)."""
    chain: list[BaseException] = []
    seen: BaseException | None = exc
    while seen is not None and seen not in chain:
        chain.append(seen)
        seen = seen.__cause__ or seen.__context__
    for link in reversed(chain):
        found = None
        for frame in traceback.extract_tb(link.__traceback__):
            parts = Path(frame.filename).parts
            if "tst" in parts and frame.filename != __file__:
                found = f"{'/'.join(parts[parts.index('tst') :])}:{frame.lineno} in {frame.name}"
        if found is not None:
            return found
    return None


class ErrorLogMiddleware:
    """Pure ASGI, so a streamed response is never buffered."""

    def __init__(self, app: ASGIApp, path: Path) -> None:
        self.app = app
        self.path = path

    def _write(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, sort_keys=True)
        with _LOCK, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        base = {"method": scope.get("method", ""), "path": scope.get("path", "")}

        async def watch(message: Message) -> None:
            if message["type"] == "http.response.start" and message["status"] >= 500:
                self._write({**base, "status": message["status"], "error": None, "where": None})
            await send(message)

        try:
            await self.app(scope, receive, watch)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self._write({**base, "status": 500, "error": error, "where": _where(exc)})
            raise
