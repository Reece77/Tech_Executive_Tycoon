"""M23c (playtest 5) API: an event's links to the screens that matter for it, the how-to on every
greyed-out action, and the read-only display endpoints."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.loader import LoadedData

TOOLS = Path(__file__).resolve().parents[3] / "tools"
BASE = "/api/saves/{}"


def tool(name: str) -> Any:
    sys.path.insert(0, str(TOOLS))
    return __import__(name)


@pytest.fixture
def saves(tmp_path: Path) -> Path:
    return tmp_path / "saves"


@pytest.fixture
def api(saves: Path) -> Iterator[Client]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as client:
        yield Client(client)


def test_a_mine_crash_links_to_its_mine(api: Client, saves: Path, loaded: LoadedData) -> None:
    tool("e2e_m19_save").crash(saves, "crash", loaded)
    base = BASE.format("crash")
    events = api.get(f"{base}/events")
    crash = next(e for e in events["open"] if e["template_id"] == "mine_price_crash")
    mine = api.get(f"{base}/mines")["mines"][0]
    paths = [link["path"] for link in crash["links"]]
    assert paths[0] == f"products/mines?mine={mine['id']}"
    assert crash["links"][0]["label"] == mine["name"]
    assert "products/mines" in paths and "finance/statements" in paths
