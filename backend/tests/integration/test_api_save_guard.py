"""M6 sub-task 0: a second write to a busy save is a 409 `save_busy`, and a save from before
the latest migration is upgraded when a game route opens it (or refused with
`upgrade_needed`), never a 500."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.test_api_hiring import BASE, hiring_client
from tst.db import migrate, repository


def _path(tmp_path: Path) -> Path:
    return repository.save_path(tmp_path / "saves", "m1b")


def test_a_write_to_a_busy_save_is_a_409(tmp_path: Path) -> None:
    with hiring_client(tmp_path) as api:
        lock = repository._lock(_path(tmp_path))
        assert lock.acquire(blocking=False)
        try:
            body = api.post(f"{BASE}/advance", status=409)
            assert body["code"] == "save_busy" and "busy" in body["message"]
            api.post(f"{BASE}/inbox/read-all", status=409)
            assert api.get(f"{BASE}/overview")["headcount"] == 1  # reads still work
        finally:
            lock.release()
        api.post(f"{BASE}/advance")


def test_a_game_route_upgrades_an_old_save(tmp_path: Path) -> None:
    with hiring_client(tmp_path) as api:
        path = _path(tmp_path)
        api.post(f"{BASE}/advance")
        migrate.downgrade(path, "0013_rivals")
        assert migrate.current_revision(path) != migrate.head_revision()
        assert api.get(f"{BASE}/overview")["headcount"] == 1
        assert migrate.current_revision(path) == migrate.head_revision()
        api.post(f"{BASE}/advance")


def test_a_save_that_cannot_be_upgraded_is_refused_clearly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with hiring_client(tmp_path) as api:

        def broken(_path: Path) -> None:
            raise RuntimeError("no such column")

        monkeypatch.setattr(migrate, "ensure_current", broken)
        monkeypatch.setattr(migrate, "head_revision", lambda: "9999_future")
        body = api.get(f"{BASE}/overview", status=409)
        assert body["code"] == "upgrade_needed" and "older version" in body["message"]
