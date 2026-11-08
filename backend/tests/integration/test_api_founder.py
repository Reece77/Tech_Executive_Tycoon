"""M24 API (formulas.md 32.8): the founder's profile tabs, Government affairs and the founder's
actions; and the hidden-value test: the scandal risk (and a pending second story) never
reaches a response or an LLM prompt, only an exposure word."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.events.context import Kpis, build_prompt
from tst.loader import LoadedData
from tst.sim.events.director import eligible_targets
from tst.sim.events.models import GameEvent
from tst.sim.founder import personal
from tst.sim.founder.models import Influence
from tst.sim.state import GameState, influence_of, with_influence

SAVE = "founder"
BASE = f"/api/saves/{SAVE}"
PLANTED_RISK = 23.456789  # an unmistakable hidden value: exposure "medium"


@pytest.fixture
def api(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[Client, Path]]:
    save_dir = tmp_path / "saves"
    path = create_save(
        SAVE, 5, "funded_spinout", company_name="Kestrel", data=loaded, save_dir=save_dir
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client), path


def _edit(path: Path, change):  # type: ignore[no-untyped-def]
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, change(before))


def _state(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


def test_founder_tabs_and_actions(api: tuple[Client, Path]) -> None:
    client, path = api
    out = client.get(f"{BASE}/founder")
    assert out["stress"]["stress"] == 20 and not out["stress"]["burnout"]
    assert [t["key"] for t in out["persona"]["traits"]] == [
        "visionary",
        "ruthless",
        "beloved",
        "reckless",
    ]
    assert out["personal"]["cash_cents"] == 0 and out["foundation"] is None
    assert not out["foundation_form"]["can_create"]
    assert out["legacy"]["total"] == 40  # 2 x (20 + 20) - (20 + 20)
    overview = client.get(f"{BASE}/overview")
    assert overview["stress"]["stress"] == 20
    # A foundation needs $1M of personal cash.
    client.post(f"{BASE}/founder/foundation", {"cause": "health"}, status=400)
    founder = _state(path).founder_of(1)
    assert founder is not None
    _edit(path, lambda s: personal.credit(s, founder.id, 300_000_000, "exit"))
    made = client.post(f"{BASE}/founder/foundation", {"cause": "health", "name": "Kestrel Fund"})
    assert made["founder"]["foundation"]["name"] == "Kestrel Fund"
    gave = client.post(f"{BASE}/founder/gifts", {"amount_cents": 200_000_000})
    assert gave["founder"]["foundation"]["endowment_cents"] == 200_000_000
    assert gave["founder"]["personal"]["cash_cents"] == 100_000_000
    client.post(f"{BASE}/founder/gifts", {"amount_cents": 200_000_000}, status=400)
    # Lobbying.
    lobbied = client.post(
        f"{BASE}/founder/lobbying", {"region": "north_america", "monthly_dollars": 250_000}
    )
    (region,) = lobbied["founder"]["government"]["regions"]
    assert region["monthly_cents"] == 25_000_000 and region["exposure"] == "low"
    client.post(f"{BASE}/founder/lobbying", {"region": "mars", "monthly_dollars": 1}, status=400)
    client.post(f"{BASE}/founder/sell-shares", {"shares": 10}, status=400)  # not listed


def _plant(state: GameState) -> GameState:
    record = influence_of(state, 1, "north_america") or Influence(1, "north_america")
    return with_influence(state, replace(record, value=40.0, risk=PLANTED_RISK, second_story=True))


def test_scandal_risk_never_in_the_api(api: tuple[Client, Path], loaded: LoadedData) -> None:
    client, path = api
    _edit(path, _plant)
    bodies = [
        client.get(f"{BASE}/founder"),
        client.get(f"{BASE}/overview"),
        client.post(
            f"{BASE}/founder/lobbying", {"region": "north_america", "monthly_dollars": 1000}
        ),
    ]
    text = json.dumps(bodies)
    assert str(PLANTED_RISK) not in text and "23.45" not in text
    assert "second_story" not in text and '"risk"' not in text
    (region,) = bodies[0]["government"]["regions"]
    assert region["exposure"] == "medium"
    schemas = client.get("/openapi.json")["components"]["schemas"]
    founder_models = [
        "InfluenceOut",
        "GovernmentOut",
        "ScandalOut",
        "FounderOut",
        "StressOut",
        "PersonaOut",
        "PersonalOut",
        "FoundationOut",
        "LegacyOut",
    ]
    for model in founder_models:
        fields = set(schemas[model]["properties"])
        assert not {"risk", "chance", "second_story"} & fields, model


def test_scandal_risk_never_in_a_prompt(api: tuple[Client, Path], loaded: LoadedData) -> None:
    _, path = api
    _edit(path, _plant)
    state = _state(path)
    texts = []
    for template in loaded.game_data.event_templates:
        if template.category not in ("founder", "press"):
            continue
        event = GameEvent(
            id=1,
            company_id=1,
            turn=state.turn,
            template_id=template.id,
            category=template.category,
            severity="critical" if template.is_critical else template.severities[0],
            trigger=template.trigger,
            strength=1.0,
        )
        system, user = build_prompt(
            state,
            event,
            template,
            eligible_targets(state, event),
            Kpis(10**9, None, 0, 1, 0),
            loaded.balance,
            loaded.game_data,
        )
        texts.append(system + user)
    joined = "\n".join(texts)
    assert texts and str(PLANTED_RISK) not in joined and "23.45" not in joined
    assert "second_story" not in joined
