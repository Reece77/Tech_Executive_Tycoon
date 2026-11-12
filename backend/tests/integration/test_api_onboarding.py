"""M29 API (formulas.md 42): unlocks and their inbox items, Getting started, What next, the
palette, the Needs you tab, interruptions and Back up."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.helpers import open_event
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db import repository
from tst.db import unlocks as unlocks_db
from tst.loader import LoadedData
from tst.sim.state import with_company

BASE = "/api/saves/o"


@pytest.fixture
def setup(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[Client, Path]]:
    saves = tmp_path / "saves"
    path = repository.create_save(
        "o", 3, "ex_big_tech_founders", company_name="Onboard", data=loaded, save_dir=saves
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as client:
        yield Client(client), path


def _shown(api: Client) -> set[str]:
    return {s["key"] for s in api.get(f"{BASE}/unlocks")["systems"] if s["unlocked"]}


def test_a_new_game_shows_stage_one_screens_and_show_everything_shows_all(
    setup: tuple[Client, Path],
) -> None:
    api, _ = setup
    out = api.get(f"{BASE}/unlocks")
    shown = _shown(api)
    assert "inbox" in shown and "products" in shown
    assert not ({"fabs", "mines", "world", "group", "exploration"} & shown)
    assert out["fresh"] == []
    settings = api.get("/api/settings/ui/onboarding")
    assert settings == {"show_everything": False, "guided_first_year": True, "stop_on": "major"}
    api.call("PUT", "/api/settings/ui/onboarding", json={**settings, "show_everything": True})
    assert _shown(api) == {s["key"] for s in out["systems"]}


def test_a_stage_rise_writes_one_unlock_item(
    setup: tuple[Client, Path], loaded: LoadedData
) -> None:
    api, path = setup
    with repository.write_session(path) as session:
        before = repository.load_state(session)
        after = with_company(before, replace(before.player, stage=2))
        assert unlocks_db.announce(session, before, after, loaded) == 3
        assert unlocks_db.announce(session, before, after, loaded) == 0  # once only
    out = api.get(f"{BASE}/unlocks")
    offices = next(s for s in out["systems"] if s["key"] == "offices")
    assert offices["unlocked"] and offices["item_id"] is not None  # announced, so it stays
    assert sorted(out["fresh"]) == ["offices", "rankings", "research"]
    items = api.get(f"{BASE}/inbox?kind=unlock")["items"]
    assert len(items) == 3 and items[0]["link_kind"] == "guide"
    nxt = api.get(f"{BASE}/what-next")["items"]
    assert any(i["key"] == "unlock" for i in nxt) and len(nxt) <= 5


def test_exploration_opens_early_from_markets(setup: tuple[Client, Path]) -> None:
    api, _ = setup
    out = api.post(f"{BASE}/unlocks/exploration/open")
    assert next(s for s in out["systems"] if s["key"] == "exploration")["unlocked"]
    api.post(f"{BASE}/unlocks/exploration/open")  # again: no second item
    assert len(api.get(f"{BASE}/inbox?kind=unlock")["items"]) == 1
    api.post(f"{BASE}/unlocks/fabs/open", status=404)


def test_getting_started_and_dismiss(setup: tuple[Client, Path]) -> None:
    api, _ = setup
    gs = api.get(f"{BASE}/getting-started")
    assert gs["visible"] and gs["months_left"] == 12 and len(gs["steps"]) == 7
    assert not any(s["done"] for s in gs["steps"])
    assert not api.post(f"{BASE}/getting-started/dismiss")["visible"]
    assert not api.get(f"{BASE}/getting-started")["visible"]


def test_palette_lists_people_and_rivals(setup: tuple[Client, Path]) -> None:
    api, _ = setup
    entries = api.get(f"{BASE}/palette")["entries"]
    kinds = {e["kind"] for e in entries}
    assert {"person", "rival"} <= kinds
    founder = next(e for e in entries if e["kind"] == "person")
    assert founder["detail"] == "Founder" and founder["path"].startswith("people/")


def test_needs_you_and_critical_only_interruptions(
    setup: tuple[Client, Path], loaded: LoadedData
) -> None:
    api, path = setup
    event_id = open_event(path, loaded, severity="major")
    needs = api.get(f"{BASE}/inbox?needs_you=true")
    assert [i["link_id"] for i in needs["items"]] == [event_id]
    assert api.get(f"{BASE}/events")["blocking_event_ids"] == [event_id]
    api.post(f"{BASE}/advance", status=409)  # major events stop Continue by default
    settings = api.get("/api/settings/ui/onboarding")
    api.call("PUT", "/api/settings/ui/onboarding", json={**settings, "stop_on": "critical"})
    assert api.get(f"{BASE}/events")["blocking_event_ids"] == []
    assert api.get(f"{BASE}/holiday")["default_stop"] == "critical"
    before = api.get(f"{BASE}/overview")["turn"]
    assert api.post(f"{BASE}/advance")["turn"] == before + 1  # answered with its first choice
    with repository.open_session(path) as session:
        event = repository.load_state(session).event(event_id)
    assert event is not None and event.status == "answered"


def test_back_up_now(setup: tuple[Client, Path]) -> None:
    api, _ = setup
    made = api.post(f"{BASE}/backups", status=201)
    assert made["kind"] == "manual"
    listed = api.get(f"{BASE}/backups")
    assert made["backup_id"] in [b["backup_id"] for b in listed]


def test_a_save_from_before_m29_shows_what_it_already_uses(
    setup: tuple[Client, Path], loaded: LoadedData
) -> None:
    api, path = setup
    from tst.db.state_io import sync_state

    with repository.write_session(path) as session:
        state = repository.load_state(session)
        sync_state(session, state, with_company(state, replace(state.player, stage=3)))
    shown = _shown(api)
    assert {"offices", "research", "infrastructure", "hardware"} <= shown
    answer = api.get(f"{BASE}/events")
    assert answer["blocking_event_id"] is None
    repository.run_turn(path, loaded, block_major=True)
    assert api.get(f"{BASE}/inbox?kind=unlock")["items"] == []  # already in use: no items


def test_the_api_serves_the_built_front_end(tmp_path: Path) -> None:
    from tst.api.app import serve_frontend

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>menu</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    app = create_app()
    serve_frontend(app, dist)
    with TestClient(app) as client:
        assert client.get("/").text == "<html>menu</html>"
        assert client.get("/game/x/inbox").text == "<html>menu</html>"  # deep links load
        assert client.get("/assets/app.js").text == "console.log(1)"
        assert client.get("/api/meta/scenarios").status_code == 200
        assert client.get("/api/nothing-here").status_code == 404
        assert client.get("/../secret").text == "<html>menu</html>"
