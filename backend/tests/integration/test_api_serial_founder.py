"""Serial founder through the API (M15b addendum 10): sell, found again, keep playing; each
company's History and Hall of Fame stay apart."""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.loader import LoadedData

SAVE = "serial"
BASE = f"/api/saves/{SAVE}"
TOOLS = Path(__file__).resolve().parents[3] / "tools"


def _tool(name: str) -> ModuleType:
    import sys

    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def api(tmp_path: Path, loaded: LoadedData) -> Iterator[Client]:
    save_dir = tmp_path / "saves"
    _tool("e2e_m14_save").exit_offer(save_dir, SAVE, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client)


def _sell(client: Client) -> None:
    for _ in range(6):
        events = [e for e in client.get(f"{BASE}/events")["open"] if e["status"] == "open"]
        if not events:
            break
        event = events[0]
        client.post(f"{BASE}/events/{event['event_id']}/choose", {"choice": "A"})
        if client.get(f"{BASE}/finance/game-over")["game_state"] == "exit":
            return
    raise AssertionError("the takeover offer never came")


def test_sell_found_again_and_play_on(api: Client) -> None:
    client = api
    _sell(client)
    over = client.get(f"{BASE}/finance/game-over")
    assert over["can_found_again"] and over["exit_proceeds_cents"] > over["min_new_cash_cents"]
    client.post(f"{BASE}/advance", status=409)  # the game waits for the choice
    keep = over["exit_proceeds_cents"] // 2
    out = client.post(
        f"{BASE}/exit/found-again", {"company_name": "Second Act", "keep_cents": keep}
    )
    assert out["game_state"] == "active" and out["company_name"] == "Second Act"
    overview = client.get(f"{BASE}/overview")
    assert overview["company_name"] == "Second Act"
    client.post(f"{BASE}/advance")
    companies = client.get(f"{BASE}/history/companies")
    assert [c["name"] for c in companies] == ["Kestrel", "Second Act"]
    assert [c["current"] for c in companies] == [False, True]
    assert companies[0]["proceeds_cents"] == over["exit_proceeds_cents"]
    old = companies[0]["company_id"]
    mine = [r["title"] for r in client.get(f"{BASE}/history/timeline")["rows"]]
    theirs = [r["title"] for r in client.get(f"{BASE}/history/timeline?company_id={old}")["rows"]]
    assert "You founded Second Act" in mine
    assert any(t.startswith("You sold the company") for t in theirs)
    assert "You founded Second Act" not in theirs
    client.get(f"{BASE}/history/hall-of-fame?company_id={old}")
    client.get(f"{BASE}/history/timeline?company_id=99999", status=404)


def test_retire_ends_it(api: Client) -> None:
    _sell(api)
    out = api.post(f"{BASE}/exit/retire")
    assert out["game_state"] == "retired"
    over = api.get(f"{BASE}/finance/game-over")
    assert over["game_state"] == "retired" and not over["can_found_again"]
    assert over["exit_buyer"]
    api.post(f"{BASE}/exit/retire", status=400)
