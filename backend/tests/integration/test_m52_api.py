"""M52 through the API (formulas.md 66.1-66.2, ADR-0026): the Editor's options, opening a start,
checking with reasons, the scenario files (create, update, list, read, export, import, delete),
the preview, starting a game from a custom scenario (its copy kept in the save, replayed from
it), and the custom results kept apart from M51's. The editor never shows or sets a hidden
value."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.custom_io import stored_custom
from tst.db.repository import read_session, read_state, replay_save
from tst.loader import LoadedData

HIDDEN = ("potential", "hidden", "trait", "true_grade", "ambition", "loyalty")


@pytest.fixture
def save_dir(tmp_path: Path) -> Path:
    return tmp_path / "saves"


@pytest.fixture
def client(save_dir: Path) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as c:
        yield c


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def test_the_editor_lists_the_loaded_data(client: TestClient, loaded: LoadedData) -> None:
    ed = client.get("/api/editor").json()
    d = loaded.game_data
    assert {c["key"] for c in ed["categories"]} == {
        c.key for c in d.categories if c.markets and not c.pseudo
    }
    assert [i["name"] for i in ed["incumbents"]] == [c.name for c in d.incumbents]
    assert ed["ranges"]["market_mult_range"] == {"lo": 0.5, "hi": 2.0}
    assert [s["key"] for s in ed["starts"]][:2] == ["blank_2008", "blank_2010"]
    assert len(ed["starts"]) == 2 + len(d.historical)
    cars = next(c for c in ed["categories"] if c["key"] == "vehicles")
    assert cars["market_editable"] is False


def test_no_editor_route_shows_or_sets_a_hidden_value(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    editor_paths = [p for p in schema["paths"] if "/editor" in p or "/scenarios/custom" in p]
    assert len(editor_paths) >= 8
    refs: set[str] = set()

    def walk(v: object) -> None:
        if isinstance(v, dict):
            for k, x in v.items():
                if k == "$ref":
                    refs.add(str(x).rsplit("/", 1)[-1])
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    for p in editor_paths:
        walk(schema["paths"][p])
    seen: set[str] = set()
    todo = list(refs)
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        comp = schema["components"]["schemas"][name]
        walk(comp)
        todo.extend(refs - seen)
    fields = {f for n in seen for f in schema["components"]["schemas"][n].get("properties", {})}
    assert not [f for f in fields if any(h in f for h in HIDDEN)], sorted(fields)


def test_open_check_save_list_export_import_delete(client: TestClient, save_dir: Path) -> None:
    spec = client.get("/api/editor/open/ev_maker").json()
    assert spec["opened_from"] == "ev_maker" and spec["key"] == "ev-maker"
    spec["key"] = "my-ev"
    spec["cash_dollars"] *= 2
    check = client.post("/api/editor/check", json=spec).json()
    assert check["valid"] and len(check["sha256"]) == 64
    bad = {**spec, "cash_dollars": 10**13}
    refused = client.post("/api/editor/check", json=bad).json()
    assert not refused["valid"] and "starting cash" in refused["reasons"][0]
    r = client.post("/api/scenarios/custom", json=bad)
    assert r.status_code == 400 and "starting cash" in r.json()["message"]
    r = client.post("/api/scenarios/custom", json=spec)
    assert r.status_code == 201, r.text
    assert client.post("/api/scenarios/custom", json=spec).status_code == 409
    spec["label"] = "My EV maker"
    assert client.put("/api/scenarios/custom/my-ev", json=spec).status_code == 200
    cards = client.get("/api/scenarios/custom").json()
    assert [(c["slug"], c["label"], c["best"]) for c in cards] == [("my-ev", "My EV maker", None)]
    assert cards[0]["sha256"] == client.post("/api/editor/check", json=spec).json()["sha256"]
    exported = client.get("/api/scenarios/custom/my-ev/export").json()
    assert exported["filename"] == "my-ev.yaml"
    r = client.post("/api/scenarios/custom-import", json={"text": exported["text"]})
    assert r.status_code == 409  # its own name exists
    r = client.post(
        "/api/scenarios/custom-import", json={"text": exported["text"], "slug": "shared"}
    )
    assert r.status_code == 201 and r.json()["key"] == "shared"
    r = client.post("/api/scenarios/custom-import", json={"text": "cash_dollars: [1"})
    assert r.status_code == 400 and "not valid YAML" in r.json()["message"]
    assert client.delete("/api/scenarios/custom/shared").status_code == 204
    assert client.get("/api/scenarios/custom/shared").status_code == 404
    assert sorted(p.name for p in (save_dir / "scenarios").iterdir()) == ["my-ev.yaml"]


def test_a_custom_game_starts_keeps_its_copy_and_replays(
    client: TestClient, save_dir: Path, loaded: LoadedData
) -> None:
    spec = client.get("/api/editor/open/platform_war").json()
    spec["key"] = "phones"
    spec["cash_dollars"] = 50_000_000
    spec["overrides"] = {"rivals": {"Microsoft": {"present": False}}}
    assert client.post("/api/scenarios/custom", json=spec).status_code == 201
    preview = client.post("/api/editor/preview", json=spec).json()
    assert preview["cash_cents"] == 50_000_000 * 100 and preview["removed"] == ["Microsoft"]
    assert not _keys(preview) & set(HIDDEN)
    r = client.post(
        "/api/saves",
        json={
            "name": "phones",
            "seed": 4,
            "scenario": "garage_bootstrap",
            "company_name": "Kestrel",
            "custom": "phones",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["mode"] == "custom" and r.json()["score"] is None
    path = save_dir / "phones.tst.sqlite"
    stored = stored_custom(path)
    assert stored is not None and stored.slug == "phones"
    with read_session(path) as session:
        state = read_state(session)
    assert state.mode is not None and state.mode.scenario == "custom/phones"
    assert state.mode.scenario_sha256 == stored.sha256
    # editing or deleting the file later never changes the game (ADR-0026 point 4)
    assert client.delete("/api/scenarios/custom/phones").status_code == 204
    assert client.post("/api/saves/phones/advance").status_code == 200
    copy = replay_save(path, save_dir, "phones-replay", loaded)
    with read_session(copy) as session:
        again = read_state(session)
    assert again.mode == read_state_of(path).mode and again.turn == read_state_of(path).turn


def read_state_of(path: Path):  # type: ignore[no-untyped-def]
    with read_session(path) as session:
        return read_state(session)


def test_custom_results_are_kept_apart(save_dir: Path) -> None:
    from tst.profile import results as kept

    assert kept.results_path(save_dir, "p", custom=True).name == "p.custom.json"
    assert kept.results_path(save_dir, "p").name == "p.json"
    assert json.dumps(kept.load(save_dir, "p", custom=True)) == "{}"
