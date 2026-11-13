"""Continue on the M9 practice save (tools/e2e_m9_save.py geo), as M9's e2e flow (c) plays it.

PR #48's e2e run refused that flow's Continue with 409: the trace showed `save_busy`, Continue
sent while the Bangalore search's POST still held the save's write lock (a second writer is
refused at once, M6 sub-task 0). Here: after the search has finished, Continue plays the month
under either Interruptions setting (M29, 42.4) and candidates arrive in Bangalore; while a
write is in progress, Continue is refused as busy and retryable, and plays once it finishes.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db import repository

TOOLS = Path(__file__).resolve().parents[3] / "tools"
NAME = "m9-geo"
BASE = f"/api/saves/{NAME}"


@pytest.fixture
def geo(tmp_path: Path) -> Iterator[tuple[Client, Path]]:
    saves = tmp_path / "saves"
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    assert importlib.import_module("e2e_m9_save").main(["geo", str(saves), NAME]) == 0
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as client:
        yield Client(client), repository.save_path(saves, NAME)


def _search_bangalore(api: Client) -> None:
    api.call(
        "POST",
        f"{BASE}/recruitment/searches",
        201,
        json={"role": "software_engineer", "channel": "job_post", "city": "bangalore"},
    )


def _answer_blocking(api: Client) -> None:
    """What the e2e helper does before Continue: the first choice on each blocking event."""
    for event_id in api.get(f"{BASE}/events")["blocking_event_ids"]:
        api.post(f"{BASE}/events/{event_id}/choose", json={"choice": "A"})


@pytest.mark.parametrize("stop_on", ["major", "critical"])
def test_continue_after_a_bangalore_search_plays_the_month(
    geo: tuple[Client, Path], stop_on: str
) -> None:
    api, _ = geo
    api.call(
        "PUT",
        "/api/settings/ui/onboarding",
        json={"show_everything": False, "guided_first_year": True, "stop_on": stop_on},
    )
    turn = api.get(f"{BASE}/overview")["turn"]
    _search_bangalore(api)
    _answer_blocking(api)
    played = api.post(f"{BASE}/advance")
    assert played["turn"] == turn + 1
    cities = {c["city"] for c in api.get(f"{BASE}/recruitment/candidates")}
    assert "bangalore" in cities, cities


def test_continue_during_a_write_is_busy_then_plays(geo: tuple[Client, Path]) -> None:
    api, path = geo
    turn = api.get(f"{BASE}/overview")["turn"]
    _answer_blocking(api)
    with repository.write_session(path):  # a write in progress, as the search's POST was
        busy = api.call("POST", f"{BASE}/advance", 409)
    assert busy["code"] == "save_busy"
    assert busy["retryable"] is True
    assert api.get(f"{BASE}/overview")["turn"] == turn  # nothing played
    assert api.post(f"{BASE}/advance")["turn"] == turn + 1
