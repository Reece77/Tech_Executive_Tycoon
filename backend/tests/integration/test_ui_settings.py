"""Saved column views (M7b sub-task 5): saves/ui_settings.json beside the saves, shared by
every save and never written into one."""

from __future__ import annotations

from pathlib import Path

from tests.integration.test_api_hiring import hiring_client
from tst.db import repository

VIEW = {
    "name": "Pay review",
    "visibility": {"age": False},
    "order": ["name", "salary", "morale"],
    "sort": [{"id": "salary", "desc": True}],
}


def test_views_persist_beside_the_saves(tmp_path: Path) -> None:
    with hiring_client(tmp_path) as api:
        assert api.get("/api/settings/ui") == {"tables": {}}
        res = api.client.put(
            "/api/settings/ui/tables/people.overview",
            json={"views": [VIEW], "current": "Pay review"},
        )
        assert res.status_code == 200, res.text
        other = api.client.put(
            "/api/settings/ui/tables/history.timeline", json={"views": [], "current": "Default"}
        )
        assert other.status_code == 200
        stored = api.get("/api/settings/ui")["tables"]
        assert stored["people.overview"]["current"] == "Pay review"
        assert stored["people.overview"]["views"][0]["sort"] == [{"id": "salary", "desc": True}]
        assert "history.timeline" in stored
    path = tmp_path / "saves" / "ui_settings.json"
    assert path.is_file()
    save = repository.save_path(tmp_path / "saves", "m1b")
    assert b"Pay review" not in save.read_bytes()  # never in a save file


def test_bad_views_are_refused(tmp_path: Path) -> None:
    with hiring_client(tmp_path) as api:
        put = api.client.put
        url = "/api/settings/ui/tables/people.overview"
        default = {**VIEW, "name": "Default"}
        assert put(url, json={"views": [default], "current": "Default"}).status_code == 422
        twice = {"views": [VIEW, VIEW], "current": "Default"}
        assert put(url, json=twice).status_code == 422
        assert put(url, json={"views": [], "current": "Missing"}).status_code == 422
        bad_id = "/api/settings/ui/tables/Bad%20Id"
        assert put(bad_id, json={"views": [], "current": "Default"}).status_code == 422
