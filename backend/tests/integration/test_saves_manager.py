"""The saves manager (M7b sub-task 2): rename, duplicate, delete and restore a backup as a new
save, through the API and the CLI; Ironman refuses duplicate and restore; a busy save
refuses every action with 409 `save_busy`."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from tst.api.app import create_app
from tst.cli import app as cli_app
from tst.config import Settings, get_settings
from tst.db import migrate, repository
from tst.db import saves as saves_db
from tst.db.backup import backup_dir, periodic_backup
from tst.loader import LoadedData


@pytest.fixture
def api(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=tmp_path)
    with TestClient(app) as client:
        yield client


def _create(api: TestClient, name: str, difficulty: str = "standard") -> dict[str, Any]:
    res = api.post(
        "/api/saves",
        json={
            "name": name,
            "seed": 5,
            "scenario": "garage_bootstrap",
            "company_name": "Kestrel",
            "difficulty": difficulty,
        },
    )
    assert res.status_code == 201, res.text
    body: dict[str, Any] = res.json()
    return body


def test_list_shows_every_column(api: TestClient) -> None:
    made = _create(api, "main")
    assert made["display_name"] == "main" and made["game_state"] == "active"
    listed = api.get("/api/saves").json()
    assert [s["save_id"] for s in listed] == ["main"]
    row = listed[0]
    for key in ("company_name", "scenario_id", "difficulty", "date_label", "turn"):
        assert row[key] == made[key]
    assert row["size_bytes"] > 0 and row["last_played"] and row["busy"] is False
    assert row["ironman"] is False


def test_rename_keeps_the_company_and_the_id(api: TestClient) -> None:
    _create(api, "main")
    res = api.post("/api/saves/main/rename", json={"name": "  My  first run "})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["display_name"] == "My first run"
    assert body["company_name"] == "Kestrel" and body["save_id"] == "main"
    assert api.get("/api/saves/main/overview").json()["company_name"] == "Kestrel"
    assert api.post("/api/saves/main/rename", json={"name": " "}).status_code == 400


def test_duplicate_is_a_separate_save(api: TestClient) -> None:
    _create(api, "main")
    assert api.post("/api/saves/main/advance").status_code == 200
    res = api.post("/api/saves/main/duplicate", json={"name": "Before the raise"})
    assert res.status_code == 201, res.text
    copy = res.json()
    assert copy["save_id"] == "before-the-raise" and copy["display_name"] == "Before the raise"
    assert copy["turn"] == 1 and copy["company_name"] == "Kestrel"
    again = api.post("/api/saves/main/duplicate", json={"name": "Before the raise"}).json()
    assert again["save_id"] == "before-the-raise-2"
    assert api.post("/api/saves/before-the-raise/advance").status_code == 200
    assert api.get("/api/saves/main").json()["turn"] == 1  # the original is untouched
    assert api.get("/api/saves/before-the-raise").json()["turn"] == 2


def test_delete_removes_the_save_and_its_backups(api: TestClient, tmp_path: Path) -> None:
    _create(api, "gone")
    path = repository.save_path(tmp_path, "gone")
    periodic_backup(path, 0, 10)
    assert backup_dir(path).is_dir()
    assert api.delete("/api/saves/gone").status_code == 204
    assert not path.exists() and not backup_dir(path).exists()
    assert api.get("/api/saves").json() == []
    assert api.get("/api/saves/gone").status_code == 404
    _create(api, "gone")  # the name is free again
    assert api.get("/api/saves/gone").json()["turn"] == 0


def test_restore_makes_a_new_save_and_never_changes_the_original(
    api: TestClient, tmp_path: Path
) -> None:
    _create(api, "main")
    path = repository.save_path(tmp_path, "main")
    for _ in range(3):
        api.post("/api/saves/main/advance")
    periodic_backup(path, 3, 10)
    api.post("/api/saves/main/advance")
    backups = api.get("/api/saves/main/backups").json()
    assert [(b["kind"], b["turn"], b["date_label"]) for b in backups] == [
        ("periodic", 3, "Apr 2010")
    ]
    res = api.post(f"/api/saves/main/backups/{backups[0]['backup_id']}/restore")
    assert res.status_code == 201, res.text
    restored = res.json()
    assert restored["display_name"] == "Kestrel (restored, Apr 2010)"
    assert restored["save_id"] == "kestrel-restored-apr-2010" and restored["turn"] == 3
    assert api.get("/api/saves/main").json()["turn"] == 4
    assert api.post(f"/api/saves/{restored['save_id']}/advance").status_code == 200
    names = {s["display_name"] for s in api.get("/api/saves").json()}
    assert names == {"main", "Kestrel (restored, Apr 2010)"}
    assert api.post("/api/saves/main/backups/nope.sqlite/restore").status_code == 404


def test_a_pre_upgrade_backup_restores_at_head(
    api: TestClient, tmp_path: Path, loaded: LoadedData
) -> None:
    _create(api, "old")
    path = repository.save_path(tmp_path, "old")
    migrate.downgrade(path, "0016_events")
    migrate.ensure_current(path)  # writes the pre-migration backup
    backups = api.get("/api/saves/old/backups").json()
    assert [b["kind"] for b in backups] == ["pre_upgrade"]
    res = api.post(f"/api/saves/old/backups/{backups[0]['backup_id']}/restore")
    assert res.status_code == 201, res.text
    restored = repository.save_path(tmp_path, res.json()["save_id"])
    assert migrate.current_revision(restored) == migrate.head_revision()


def test_ironman_refuses_duplicate_and_restore_but_deletes(api: TestClient, tmp_path: Path) -> None:
    made = _create(api, "iron", difficulty="ironman")
    assert made["ironman"] is True
    path = repository.save_path(tmp_path, "iron")
    periodic_backup(path, 0, 10)
    dup = api.post("/api/saves/iron/duplicate", json={"name": "cheat"})
    assert dup.status_code == 409 and dup.json()["code"] == "ironman_save"
    backup = api.get("/api/saves/iron/backups").json()[0]["backup_id"]
    res = api.post(f"/api/saves/iron/backups/{backup}/restore")
    assert res.status_code == 409 and res.json()["code"] == "ironman_save"
    assert api.post("/api/saves/iron/rename", json={"name": "Hard mode"}).status_code == 200
    assert api.delete("/api/saves/iron").status_code == 204


def test_busy_saves_refuse_every_action(api: TestClient, tmp_path: Path) -> None:
    _create(api, "busy")
    path = repository.save_path(tmp_path, "busy")
    periodic_backup(path, 0, 10)
    backup = api.get("/api/saves/busy/backups").json()[0]["backup_id"]
    calls = [
        ("POST", "/api/saves/busy/rename", {"name": "x"}),
        ("POST", "/api/saves/busy/duplicate", {"name": "x"}),
        ("DELETE", "/api/saves/busy", None),
        ("POST", f"/api/saves/busy/backups/{backup}/restore", None),
    ]
    for hold in ("lock", "holiday"):
        lock = repository._lock(path)
        token = None
        if hold == "lock":
            assert lock.acquire(blocking=False)
        else:
            token = repository.reserve(path)
        try:
            assert api.get("/api/saves/busy").json()["busy"] is True
            for method, url, body in calls:
                res = api.request(method, url, json=body)
                assert res.status_code == 409, (hold, url, res.text)
                assert res.json()["code"] == "save_busy"
        finally:
            if token is None:
                lock.release()
            else:
                repository.release(path, token)
    assert path.exists() and len(api.get("/api/saves").json()) == 1


def test_cli_saves(loaded: LoadedData, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TST_SAVE_DIR", str(tmp_path))
    run = CliRunner()
    path = repository.create_save(
        "cli", 5, "garage_bootstrap", company_name="Kestrel", data=loaded, save_dir=tmp_path
    )
    periodic_backup(path, 0, 10)
    out = run.invoke(cli_app, ["saves", "list"])
    assert out.exit_code == 0 and "cli" in out.output and "Kestrel" in out.output
    out = run.invoke(cli_app, ["saves", "rename", "--save", "cli", "--name", "Main run"])
    assert out.exit_code == 0 and "Main run" in out.output
    out = run.invoke(cli_app, ["saves", "duplicate", "--save", "cli", "--name", "Copy"])
    assert out.exit_code == 0 and "copy" in out.output
    out = run.invoke(cli_app, ["saves", "restore", "--save", "cli"])
    assert out.exit_code == 0 and "periodic" in out.output
    backup = saves_db.backups(path)[0].backup_id
    out = run.invoke(cli_app, ["saves", "restore", "--save", "cli", "--backup", backup])
    assert out.exit_code == 0 and "restored, Jan 2010" in out.output
    bad = run.invoke(cli_app, ["saves", "delete", "--save", "copy", "--confirm", "nope"])
    assert bad.exit_code == 1
    out = run.invoke(cli_app, ["saves", "delete", "--save", "copy", "--confirm", "copy"])
    assert out.exit_code == 0
    slugs = {s.slug for s in saves_db.list_files(tmp_path)}
    assert slugs == {"cli", "kestrel-restored-jan-2010"}
