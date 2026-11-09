"""M25 sub-task 4: the data editor and mods. The editor lists the files with specs and
comments; an invalid mod is refused with the loader's message; a modded game plays with
its mod, is flagged, earns no achievements, and reloads identically after its mod file is
edited or deleted."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db import repository
from tst.db.models import TurnSnapshotRow
from tst.loader import LoadedData
from tst.mods import store
from tst.profile import store as profile

BRAND = ["companies", "@name=Salesforce", "products", "@name=Sales Cloud", "brand"]


class ModClient(Client):
    """The hidden-field-checking client, with PUT and DELETE."""

    def put(self, url: str, json: Any = None, status: int = 200) -> Any:
        return self.call("PUT", url, status, json=json)

    def delete(self, url: str, status: int = 204) -> None:
        res = self.client.request("DELETE", url)
        assert res.status_code == status, (url, res.status_code, res.text)


@pytest.fixture
def api(tmp_path: Path) -> Iterator[ModClient]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=tmp_path / "saves")
    with TestClient(app) as tc:
        yield ModClient(tc)


def _new(api: ModClient, name: str, mod: str | None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": name,
        "seed": 5,
        "scenario": "garage_bootstrap",
        "company_name": f"{name} Co",
        "mission": ["ai", "enterprise"],
    }
    if mod:
        body["mod"] = mod
    out: dict[str, Any] = api.post("/api/saves", body, status=201)
    return out


def _brand(api: ModClient, save: str) -> float:
    rivals = api.get(f"/api/saves/{save}/rivals")["rivals"]
    sf = next(r for r in rivals if r["name"] == "Salesforce")
    profile_ = api.get(f"/api/saves/{save}/rivals/{sf['company_id']}")
    return float(profile_["segments"][0]["brand"])


def test_the_editor_lists_files_with_specs_and_comments(api: ModClient) -> None:
    files = [f["file"] for f in api.get("/api/mods/files")]
    assert files[:6] == [
        "incumbents.yaml",
        "entrants.yaml",
        "categories.yaml",
        "cities.yaml",
        "scenarios.yaml",
        "balance.yaml",
    ]
    balance = api.get("/api/mods/files/balance.yaml")
    assert balance["spec"]["kind"] == "object"
    names = {f["name"] for f in balance["spec"]["fields"]}
    assert {"company", "backup", "market"} <= names
    assert "cents per month" in balance["comments"]["company.base_monthly_cost_cents"]
    rivals = api.get("/api/mods/files/incumbents.yaml")
    companies = next(f for f in rivals["spec"]["fields"] if f["name"] == "companies")
    assert companies["spec"]["kind"] == "list" and companies["spec"]["item"]["kind"] == "object"
    assert "company stage" in rivals["comments"]["field:stage"]
    api.get("/api/mods/files/accounts.yaml", status=404)


def test_an_invalid_mod_is_refused_with_the_loaders_message(api: ModClient, tmp_path: Path) -> None:
    bad = api.put(
        "/api/mods/broken",
        {"changes": [{"file": "balance.yaml", "path": ["backup", "every_n_turns"], "value": -3}]},
        status=400,
    )
    assert bad["code"] == "invalid_mod" and bad["message"].startswith("balance.yaml:")
    assert "every_n_turns" in bad["message"]
    assert not (tmp_path / "saves" / "mods" / "broken.yaml").exists()  # nothing written
    api.put(
        "/api/mods/x",
        {"changes": [{"file": "balance.yaml", "path": ["nope"], "value": 1}]},
        status=400,
    )
    api.put("/api/mods/Bad Name", {"changes": []}, status=400)


def test_a_modded_game_plays_with_its_mod_and_is_flagged(api: ModClient, tmp_path: Path) -> None:
    saved = api.put(
        "/api/mods/half-brand",
        {
            "description": "Salesforce at half brand",
            "changes": [{"file": "incumbents.yaml", "path": BRAND, "value": 40}],
        },
    )
    assert saved["changes"] == [{"file": "incumbents.yaml", "path": BRAND, "value": 40}]
    assert [m["name"] for m in api.get("/api/mods")] == ["half-brand"]
    text = (tmp_path / "saves" / "mods" / "half-brand.yaml").read_text()
    assert "brand: 40" in text and "mod_format: 1" in text
    merged = api.get("/api/mods/files/incumbents.yaml?mod=half-brand")
    assert merged["value"]["companies"][0]["products"][0]["brand"] == 40
    assert merged["base"]["companies"][0]["products"][0]["brand"] == 80

    modded = _new(api, "modded", "half-brand")
    plain = _new(api, "plain", None)
    assert modded["mod_name"] == "half-brand" and plain["mod_name"] is None
    assert _brand(api, "modded") == 40 and _brand(api, "plain") == 80
    listed = {s["save_id"]: s["mod_name"] for s in api.get("/api/saves")}
    assert listed == {"modded": "half-brand", "plain": None}
    ach = api.get("/api/saves/modded/achievements")
    assert not ach["eligible"] and "Modded" in ach["reason"]
    assert api.get("/api/saves/modded/history/hall-of-fame")["mod_name"] == "half-brand"
    assert api.get("/api/saves/plain/history/hall-of-fame")["mod_name"] is None
    api.post("/api/saves/modded/advance")
    earned = profile.load(tmp_path / "saves").earned
    assert all(e["save"] != "modded" for e in earned.values())  # modded games earn none
    api.delete("/api/mods/half-brand", status=204)
    assert api.get("/api/mods") == []


def _snapshots(path: Path) -> list[Any]:
    with repository.open_session(path) as session:
        rows = session.scalars(select(TurnSnapshotRow).order_by(TurnSnapshotRow.id))
        return [(r.turn, r.company_id, json.dumps(r.kpis, sort_keys=True)) for r in rows]


def test_a_modded_save_reloads_identically_after_its_mod_changes(
    api: ModClient, tmp_path: Path, loaded: LoadedData
) -> None:
    change = {"file": "incumbents.yaml", "path": BRAND, "value": 40}
    api.put("/api/mods/m", {"changes": [change]})
    _new(api, "a", "m")
    _new(api, "b", "m")
    save_dir = tmp_path / "saves"
    a, b = (repository.existing_save_path(save_dir, s) for s in ("a", "b"))
    recorded = store.save_mod(a)
    assert recorded is not None and recorded.name == "m" and recorded.hash
    for _ in range(3):
        api.post("/api/saves/a/advance")
    # The mod file changes, then goes: b plays with its own copy all the same.
    change["value"] = 5
    api.put("/api/mods/m", {"changes": [change]})
    assert _brand(api, "b") == 40
    store.delete_mod(save_dir, "m")
    for _ in range(3):
        api.post("/api/saves/b/advance")
    assert _brand(api, "b") == _brand(api, "a")
    assert _snapshots(a) == [(t, c, k) for t, c, k in _snapshots(b)]
    again = store.data_for_save(b, Settings().data_dir, loaded)
    assert again.mod_hash == recorded.hash
    assert (
        store.data_for_save(repository.save_path(save_dir, "none"), Settings().data_dir, loaded)
        is loaded
    )


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(k) for k in value} | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def test_the_editor_withholds_every_name_the_api_forbids() -> None:
    """tst.mods.hidden mirrors the API's hidden-name rule: every key in an editable file that
    the rule forbids is withheld (the Client wrapper then checks each editor response)."""
    import yaml

    from tests.integration.test_api import forbidden
    from tst.mods.hidden import withheld
    from tst.mods.schema import editable_files

    names: set[str] = set()
    for file in editable_files():
        names |= _keys(yaml.safe_load((Settings().data_dir / file).read_text()))
    flagged = {n for n in names if forbidden(n)}
    assert flagged, "the files do hold names the API forbids"
    assert {n for n in flagged if not withheld(n)} == set()


def test_a_spoiler_change_without_the_toggle_is_refused(api: ModClient) -> None:
    path = ["companies", "@name=Salesforce", "cash_months"]
    out = api.put(
        "/api/mods/rich", {"changes": [{"file": "incumbents.yaml", "path": path, "value": 1}]}, 400
    )
    assert out["code"] == "invalid_mod" and "spoiler field" in out["message"]


def test_a_market_twice_as_big(api: ModClient) -> None:
    """Reece's manual check: AI models' addressable customers doubled in every segment."""
    cats = api.get("/api/mods/files/categories.yaml")["base"]["categories"]
    ai = next(c for c in cats if c["key"] == "ai_models")
    changes = [
        {
            "file": "categories.yaml",
            "path": [
                "categories",
                "@key=ai_models",
                "markets",
                f"@segment={m['segment']}",
                "addressable",
            ],
            "value": m["addressable"] * 2,
        }
        for m in ai["markets"]
    ]
    out = api.put("/api/mods/big-ai", {"changes": changes})
    assert len(out["changes"]) == len(ai["markets"])
    _new(api, "bigai", "big-ai")
    market = api.get("/api/saves/bigai/markets/ai_models")
    sizes = {s["segment"]: s["addressable"] for s in market["segments"]}
    assert sizes == {m["segment"]: m["addressable"] * 2 for m in ai["markets"]}


# --- PM ruling 2026-11-08: "Show spoiler fields" ----------------------------------------------


def _raw(api: ModClient, url: str) -> Any:
    """An editor response without the hidden-key check (spoilers may name those keys)."""
    res = api.client.get(url)
    assert res.status_code == 200, (url, res.text)
    return res.json()


def test_spoiler_fields_show_and_edit_only_behind_the_toggle(api: ModClient) -> None:
    from tests.integration.test_api import find_forbidden_keys

    off = api.get("/api/mods/files/incumbents.yaml")  # the checking client: none by default
    assert "cash_months" not in off["base"]["companies"][0]
    on = _raw(api, "/api/mods/files/incumbents.yaml?spoilers=true")
    assert on["base"]["companies"][0]["cash_months"] > 0
    fields = {f["name"] for f in on["spec"]["fields"][0]["spec"]["item"]["fields"]}
    assert "cash_months" in fields
    assert find_forbidden_keys(on) != []  # they are there only because the toggle is on

    path = ["companies", "@name=Salesforce", "cash_months"]
    change = {"file": "incumbents.yaml", "path": path, "value": 6}
    refused = api.put("/api/mods/rich", {"changes": [change]}, 400)
    assert "Show spoiler fields" in refused["message"]
    res = api.client.put("/api/mods/rich", json={"changes": [change], "spoilers": True})
    assert res.status_code == 200 and res.json()["changes"] == [change]
    assert api.get("/api/mods/rich")["changes"] == []  # hidden again with the toggle off
    assert _raw(api, "/api/mods/rich?spoilers=true")["changes"] == [change]
    merged = _raw(api, "/api/mods/files/incumbents.yaml?mod=rich&spoilers=true")
    assert merged["value"]["companies"][0]["cash_months"] == 6
    plain = api.get("/api/mods/files/incumbents.yaml?mod=rich")
    assert "cash_months" not in plain["value"]["companies"][0]


def _editor_responses(api: ModClient) -> str:
    files = [f["file"] for f in _raw(api, "/api/mods/files")]
    out: dict[str, Any] = {"files": files, "mods": _raw(api, "/api/mods?spoilers=true")}
    for f in files:
        for flag in ("false", "true"):
            out[f"{f}:{flag}"] = _raw(api, f"/api/mods/files/{f}?spoilers={flag}")
    return json.dumps(out, sort_keys=True)


def test_editor_routes_return_no_save_state(api: ModClient) -> None:
    """The editor reads data files and mod overlays only: its responses are the same with
    no save at all and with a played save beside them, and never name a save."""
    spec = api.get("/openapi.json")
    editor = [p for p in spec["paths"] if p.startswith("/api/mods")]
    assert editor and all("save_id" not in p for p in editor)
    before = _editor_responses(api)
    _new(api, "zxqsave", None)
    api.post("/api/saves/zxqsave/advance")
    after = _editor_responses(api)
    assert after == before
    assert "zxqsave" not in after and "zxqsave Co" not in after


def test_game_routes_never_return_forbidden_keys(api: ModClient) -> None:
    """Every game route on a save (GET, the save id its only path parameter) still keeps the
    hidden-name rule; the toggle reaches no route under /api/saves."""
    from tests.integration.test_api import find_forbidden_keys

    _new(api, "rules", None)
    for _ in range(2):
        api.post("/api/saves/rules/advance")
    spec = api.get("/openapi.json")
    checked = 0
    for path, ops in spec["paths"].items():
        if "get" not in ops or not path.startswith("/api/saves/{save_id}"):
            continue
        if set(re.findall(r"\{(\w+)\}", path)) != {"save_id"}:
            continue
        for url in (path, path + "?spoilers=true"):
            res = api.client.get(url.replace("{save_id}", "rules"))
            if res.status_code == 200 and "json" in res.headers.get("content-type", ""):
                assert find_forbidden_keys(res.json()) == [], url
                checked += 1
    assert checked > 40  # the screens' routes were all reached


def test_saving_with_the_toggle_off_keeps_spoiler_changes(api: ModClient) -> None:
    spoiler = {
        "file": "incumbents.yaml",
        "path": ["companies", "@name=Salesforce", "cash_months"],
        "value": 6,
    }
    brand = {"file": "incumbents.yaml", "path": BRAND, "value": 40}
    res = api.client.put("/api/mods/both", json={"changes": [spoiler], "spoilers": True})
    assert res.status_code == 200
    api.put("/api/mods/both", {"changes": [brand]})  # edited later with the toggle off
    assert api.get("/api/mods/both")["changes"] == [brand]
    kept = _raw(api, "/api/mods/both?spoilers=true")["changes"]
    assert sorted(map(json.dumps, kept)) == sorted(map(json.dumps, [spoiler, brand]))
