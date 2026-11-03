"""M13 API: the IPO chain end to end through the engine and the API, the Stock tab and capital
actions, the CEO seat, and the planted-value test for the book-demand draw, the sentiment
behind the price (and so its future) and V_f (formulas.md 25.8)."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.repository import open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.state import listing_of, public_of, with_listing, with_public

SAVE = "kestrel"
BASE = f"/api/saves/{SAVE}"
TOOL = Path(__file__).resolve().parents[3] / "tools" / "e2e_m13_save.py"


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("e2e_m13_save", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL_MODULE = _tool()


@pytest.fixture
def api(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[Client, Path]]:
    save_dir = tmp_path / "saves"
    path = TOOL_MODULE.eligible(save_dir, SAVE, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client), path


def _continue(client: Client) -> None:
    client.post(f"{BASE}/advance")


def _answer_all(client: Client) -> list[str]:
    seen = []
    for event in client.get(f"{BASE}/events")["open"]:
        if event["status"] == "open":
            key = event["choices"][0]["key"]
            client.post(f"{BASE}/events/{event['event_id']}/choose", {"choice": key})
            seen.append(event["category"])
    return seen


def test_ipo_chain_end_to_end(api: tuple[Client, Path], loaded: LoadedData) -> None:
    client, path = api
    out = client.get(f"{BASE}/public")
    assert out["eligible"] and out["ipo"] is None and out["stock"] is None
    assert {b["name"] for b in out["banks"]} == {"Goldman Sachs", "Morgan Stanley", "J.P. Morgan"}
    hired = client.post(f"{BASE}/public/banks", {"bank": "goldman_sachs"})
    assert hired["public"]["ipo"]["status"] == "filing"
    assert hired["energy"]["energy"] == hired["energy"]["max"] - 10
    seen: list[str] = []
    for _ in range(8):
        _continue(client)
        seen += _answer_all(client)
        out = client.get(f"{BASE}/public")
        if out["stock"] is not None:
            break
        if out["ipo"]["status"] == "pricing":
            assert out["ipo"]["demand"] in ("weak", "steady", "healthy", "strong", "very strong")
            assert {o["choice"] for o in out["ipo"]["options"]} == {"range", "raise", "cut", "pull"}
    assert seen.count("public") >= 5  # S-1, three roadshow events, pricing
    stock = out["stock"]
    assert stock is not None and stock["ticker"] == "KEST"
    assert out["stage"] == 4 and out["ipo"]["status"] == "listed"
    assert stock["history"][0]["mark"] == "listing"
    assert 3 <= len(stock["analysts"]) <= 8
    assert out["ceo"]["seat_open"] and out["ceo"]["candidates"]
    with open_session(path) as session:
        state = load_state(session)
    assert state.player.stage == 4


def _listed(api: tuple[Client, Path], loaded: LoadedData) -> tuple[Client, Path]:
    client, path = api
    TOOL_MODULE.play_chain(path, loaded)
    return client, path


def test_stock_tab_capital_actions_and_ceo(api: tuple[Client, Path], loaded: LoadedData) -> None:
    client, path = _listed(api, loaded)
    stock = client.get(f"{BASE}/public")["stock"]
    nxt = stock["next_guidance"]
    assert nxt["can_set"], nxt
    guided = client.post(
        f"{BASE}/public/guidance",
        {"revenue_cents": nxt["consensus_revenue_cents"], "margin_bp": 1000},
    )["public"]["stock"]["next_guidance"]
    assert guided["set_revenue_cents"] == nxt["consensus_revenue_cents"]
    client.post(f"{BASE}/public/guidance", {"revenue_cents": 1, "margin_bp": 0}, status=400)
    out = client.post(f"{BASE}/public/buyback", {"amount_cents": 100_000_000})
    assert out["public"]["stock"]["shares"] < stock["shares"]
    out = client.post(f"{BASE}/public/dividend", {"per_share_cents": 1})
    assert out["public"]["stock"]["capital"]["dividend_declared_cents"] == 1
    ceo = out["public"]["ceo"]
    person = ceo["candidates"][0]["person_id"]
    out = client.post(f"{BASE}/public/ceo", {"person_id": person})
    assert out["public"]["ceo"]["person_id"] == person
    _continue(client)
    _answer_all(client)
    ceo = client.get(f"{BASE}/public")["ceo"]
    assert ceo["name"]
    overridable = [d for d in ceo["decisions"] if d["can_override"]]
    if overridable:
        out = client.post(f"{BASE}/public/ceo/decisions/{overridable[0]['id']}/override")
        assert next(
            d for d in out["public"]["ceo"]["decisions"] if d["id"] == overridable[0]["id"]
        )["overridden"]
    out = client.post(f"{BASE}/public/ceo/dismiss")
    assert out["public"]["ceo"]["person_id"] is None


def test_no_response_shows_the_demand_draw_sentiment_or_value(
    api: tuple[Client, Path], loaded: LoadedData
) -> None:
    """25.8: plant distinctive hidden values and look for them in every M13 response."""
    client, path = _listed(api, loaded)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        listing = listing_of(before, 1)
        public = public_of(before, 1)
        assert listing is not None and public is not None
        state = with_listing(before, replace(listing, demand=1.98765))
        state = with_public(state, replace(public, sentiment=1.23456, value_cents=987_654_321_99))
        sync_state(session, before, state)
    blobs = [
        json.dumps(client.get(f"{BASE}/public")),
        json.dumps(client.get(f"{BASE}/events")),
        json.dumps(client.get(f"{BASE}/overview")),
        json.dumps(client.get(f"{BASE}/finance/board")),
    ]
    blob = "\n".join(blobs)
    for planted in ("1.98765", "1.988", "1.99", "1.23456", "1.235", "98765432199", "987654321"):
        assert planted not in blob, planted
    out = json.loads(blobs[0])
    assert out["ipo"]["demand"] == "strong"  # the word only
    for forbidden in ("sentiment", "value_cents", "demand_draw", "threshold"):
        assert f'"{forbidden}"' not in blobs[0], forbidden  # as a key
