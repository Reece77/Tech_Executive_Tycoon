"""M35a sub-task 2: with TST_ERROR_LOG set, the API writes every unhandled exception and 5xx
response as a JSON line, which e2e reads to fail a run (frontend/e2e/server-errors.ts)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from tst.api.error_log import ErrorLogMiddleware


def _app(log: Path) -> FastAPI:
    app = FastAPI()

    @app.get("/fine")
    def fine() -> dict[str, int]:
        return {"ok": 1}

    @app.get("/missing")
    def missing() -> JSONResponse:
        return JSONResponse({"code": "not_found"}, status_code=404)

    @app.get("/boom")
    def boom() -> dict[str, int]:
        return {}[3]  # type: ignore[index]

    @app.get("/unavailable")
    def unavailable() -> JSONResponse:
        return JSONResponse({"code": "down"}, status_code=503)

    app.add_middleware(ErrorLogMiddleware, path=log)
    return app


def test_errors_and_5xx_are_logged_and_nothing_else(tmp_path: Path) -> None:
    log = tmp_path / "errors.jsonl"
    client = TestClient(_app(log), raise_server_exceptions=False)
    assert client.get("/fine").status_code == 200
    assert client.get("/missing").status_code == 404
    assert client.get("/boom").status_code == 500
    assert client.get("/unavailable").status_code == 503
    lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert [(x["path"], x["status"]) for x in lines] == [("/boom", 500), ("/unavailable", 503)]
    assert lines[0]["error"] == "KeyError: 3"
    assert lines[0]["where"] is None  # no frame in the game's own code (tst/)
    assert lines[1]["error"] is None


def test_the_app_installs_it_only_when_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tst.api.app import create_app
    from tst.config import get_settings

    get_settings.cache_clear()
    try:
        assert not any(m.cls is ErrorLogMiddleware for m in create_app().user_middleware)
        monkeypatch.setenv("TST_ERROR_LOG", str(tmp_path / "e.jsonl"))
        get_settings.cache_clear()
        assert any(m.cls is ErrorLogMiddleware for m in create_app().user_middleware)
    finally:
        get_settings.cache_clear()
