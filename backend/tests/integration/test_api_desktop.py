"""M58: the desktop routes with a desktop context installed, and the real entry point run
headless in a subprocess (the release smoke test's steps, on this machine)."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.unit.test_desktop import KEY, release_payload
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db import repository
from tst.desktop import context, imports
from tst.desktop.paths import DesktopPaths

BACKEND = Path(__file__).resolve().parents[2]
NEW_GAME = {"name": "practice", "seed": 7, "scenario": "garage_bootstrap", "company_name": "P"}
BLOB = b"pretend installer"


@pytest.fixture
def ctx(tmp_path: Path) -> Iterator[context.DesktopContext]:
    paths = DesktopPaths(documents=tmp_path / "Documents" / "TST", app_data=tmp_path / "AppData")
    paths.make()
    launched: list[list[str]] = []
    closed: list[bool] = []

    def fetch(url: str, _timeout: float) -> bytes:
        if url.endswith(".sha256"):
            return hashlib.sha256(BLOB).hexdigest().encode()
        return json.dumps(release_payload("6.1.0")).encode()

    c = context.DesktopContext(
        paths=paths,
        version="6.0.0",
        fetch=fetch,
        stream=lambda _u, _t: iter([BLOB]),
        popen=lambda cmd, **_kw: launched.append(cmd),
        sleep=lambda _s: None,
        environ={},
        check_token=lambda t: t == "tok",
    )
    c.close = lambda: closed.append(True)
    c.launched, c.closed = launched, closed  # type: ignore[attr-defined]
    context.install(c)
    yield c
    context.install(None)


@pytest.fixture
def client(ctx: context.DesktopContext) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=ctx.paths.saves)
    with TestClient(app) as c:
        yield c


def _wait(ctx: context.DesktopContext, *states: str) -> None:
    deadline = time.monotonic() + 30
    while ctx.update_state not in states:
        assert time.monotonic() < deadline, ctx.update_state
        time.sleep(0.02)
    if ctx._thread is not None:
        ctx._thread.join(10)


def test_status_and_health(client: TestClient, ctx: context.DesktopContext) -> None:
    body = client.get("/api/desktop").json()
    assert body["desktop"] is True and body["version"] == "6.0.0"
    assert body["saves_dir"] == str(ctx.paths.saves)
    assert body["update"] is None and body["key_saved"] is False
    assert client.get("/api/health").json() == {"status": "ok", "version": "6.0.0"}


def test_api_key_is_stored_in_app_data_and_never_returned(
    client: TestClient, ctx: context.DesktopContext
) -> None:
    res = client.put("/api/desktop/api-key", json={"key": KEY})
    assert res.status_code == 200 and res.json()["key_saved"] is True
    assert KEY not in res.text and KEY not in client.get("/api/desktop").text
    assert KEY in ctx.paths.env_file.read_text()
    assert ctx.environ["ANTHROPIC_API_KEY"] == KEY
    assert client.put("/api/desktop/api-key", json={"key": "a b"}).status_code == 422
    assert client.put("/api/desktop/api-key", json={"key": ""}).json()["key_saved"] is False
    assert "ANTHROPIC_API_KEY" not in ctx.environ


def test_update_offered_verified_backed_up_then_installed(
    client: TestClient, ctx: context.DesktopContext
) -> None:
    assert client.post("/api/saves", json=NEW_GAME).status_code == 201
    client.post("/api/saves/practice/advance").raise_for_status()
    ctx.check_for_update()
    body = client.get("/api/desktop").json()
    assert body["update_state"] == "available"
    assert body["update"]["version"] == "6.1.0" and "Faster turns" in body["update"]["notes"]

    assert client.post("/api/desktop/update").status_code == 200
    _wait(ctx, "installing", "failed")
    assert ctx.update_state == "installing", ctx.update_message
    (installer,) = ctx.launched  # type: ignore[attr-defined]
    assert Path(installer[0]).read_bytes() == BLOB
    assert ctx.closed == [True]  # type: ignore[attr-defined]
    backup = ctx.backup_folder
    assert backup is not None and backup.parent == ctx.paths.update_backups
    con = sqlite3.connect(backup / "practice.tst.sqlite")
    try:
        assert con.execute("select count(*) from save_meta").fetchone()[0] == 1
    finally:
        con.close()
    # From the backup on, the game refuses writes: the backup is the saves' last state.
    res = client.post("/api/saves/practice/advance")
    assert res.status_code == 409 and res.json()["code"] == "save_busy"
    assert client.get("/api/saves").status_code == 200


def test_no_update_while_a_turn_runs(client: TestClient, ctx: context.DesktopContext) -> None:
    assert client.post("/api/saves", json=NEW_GAME).status_code == 201
    ctx.check_for_update()
    lock = repository._lock(ctx.paths.saves / "practice.tst.sqlite")
    with lock:  # what a turn holds
        res = client.post("/api/desktop/update")
    assert res.status_code == 409 and "turn" in res.json()["message"]
    assert ctx.launched == []  # type: ignore[attr-defined]
    assert client.post("/api/desktop/update/later").json()["update_state"] == "none"


def test_a_bad_checksum_installs_nothing(client: TestClient, ctx: context.DesktopContext) -> None:
    ctx.check_for_update()
    ctx.stream = lambda _u, _t: iter([b"tampered"])
    client.post("/api/desktop/update").raise_for_status()
    _wait(ctx, "failed", "installing")
    body = client.get("/api/desktop").json()
    assert body["update_state"] == "failed" and "checksum" in body["update_message"]
    assert ctx.launched == [] and ctx.backup_folder is None  # type: ignore[attr-defined]
    assert client.post("/api/saves", json=NEW_GAME).status_code == 201  # writes still allowed


def test_first_run_import(client: TestClient, ctx: context.DesktopContext, tmp_path: Path) -> None:
    old = tmp_path / "repo" / "saves"
    other = TestClient(create_app())
    other.app.dependency_overrides[get_settings] = lambda: Settings(save_dir=old)  # type: ignore[attr-defined]
    assert other.post("/api/saves", json=NEW_GAME).status_code == 201
    ctx.import_offer = imports.find_offer(ctx.paths.saves, [old])
    body = client.get("/api/desktop").json()
    assert body["import_offer"] == {"folder": str(old), "saves": ["practice"]}
    assert client.post("/api/desktop/import", json={"accept": True}).json() == {
        "imported": ["practice"]
    }
    assert client.get("/api/desktop").json()["import_offer"] is None
    assert [s["save_id"] for s in client.get("/api/saves").json()] == ["practice"]
    assert context.load_settings(ctx.paths)["import_answered"] is True


def test_focus_needs_the_instance_token(client: TestClient, ctx: context.DesktopContext) -> None:
    focused: list[bool] = []
    ctx.focus = lambda: focused.append(True)
    assert client.post("/api/desktop/focus").status_code == 403
    assert client.post("/api/desktop/focus", headers={"X-TST-Instance": "x"}).status_code == 403
    assert client.post("/api/desktop/focus", headers={"X-TST-Instance": "tok"}).status_code == 204
    assert focused == [True]


def test_outside_the_desktop_build() -> None:
    client = TestClient(create_app())
    assert client.get("/api/desktop").json()["desktop"] is False
    assert client.post("/api/desktop/update").json()["code"] == "not_desktop"
    assert client.post("/api/desktop/focus").status_code == 403


# --- the real entry point ---------------------------------------------------------------
def _get(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=10) as res:
        return json.loads(res.read())


def _post(url: str, body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read())


def _listening(port: int) -> list[str]:
    """Local addresses (hex, as /proc/net/tcp writes them) listening on `port`."""
    found = []
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        if not Path(table).is_file():
            continue
        for line in Path(table).read_text().splitlines()[1:]:
            local, state = line.split()[1], line.split()[3]
            address, hex_port = local.rsplit(":", 1)
            if state == "0A" and int(hex_port, 16) == port:
                found.append(address)
    return found


def _start(home: Path) -> subprocess.Popen[bytes]:
    env = {**os.environ, "TST_DESKTOP_HOME": str(home), "ANTHROPIC_API_KEY": ""}
    cmd = [sys.executable, "-m", "tst.desktop", "--headless", "--no-update-check"]
    return subprocess.Popen(cmd, cwd=BACKEND, env=env)


def _port(home: Path, proc: subprocess.Popen[bytes]) -> int:
    instance = home / "AppData" / "instance.json"
    deadline = time.monotonic() + 60
    while not instance.is_file():
        assert proc.poll() is None, "the desktop entry point exited"
        assert time.monotonic() < deadline, "no instance.json"
        time.sleep(0.1)
    return int(json.loads(instance.read_text())["port"])


@pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM; the release workflow covers Windows")
def test_headless_entry_point_serves_on_localhost_only(tmp_path: Path) -> None:
    proc = _start(tmp_path)
    try:
        port = _port(tmp_path, proc)
        base = f"http://127.0.0.1:{port}"
        assert _get(f"{base}/api/health")["status"] == "ok"
        assert _get(f"{base}/api/desktop")["desktop"] is True
        _post(f"{base}/api/saves", NEW_GAME)
        assert _post(f"{base}/api/saves/practice/advance")["date_label"] == "Feb 2010"
        saves = tmp_path / "Documents" / "Tech Startup Tycoon" / "saves"
        assert (saves / "practice.tst.sqlite").is_file()
        # Listening on 127.0.0.1 only: the kernel's table of listening sockets has the port
        # once, on 127.0.0.1 (0100007F), and no IPv6 or any-address socket.
        if Path("/proc/net/tcp").is_file():
            assert _listening(port) == ["0100007F"]
        # A second launch finds the first, asks it to focus and exits at once.
        second = _start(tmp_path)
        assert second.wait(timeout=60) == 0
        assert proc.poll() is None
    finally:
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=30) == 0
    assert not (tmp_path / "AppData" / "instance.json").exists()
    log = (tmp_path / "AppData" / "logs" / "desktop.log").read_text()
    assert "serving on http://127.0.0.1:" in log and "already running" in log
