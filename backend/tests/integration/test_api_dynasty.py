"""M37 API (formulas.md 52.1, 52.6): the Campaign length setting, a standard campaign's end at
December 2039 (only the choice is allowed, through the persistence path), continuing in dynasty
mode, and the hidden-value test: no mortality chance, succession draw or seeded month reaches a
response or an LLM prompt before it happens."""

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
from tst.db import repository
from tst.db.models import SaveMetaRow
from tst.db.repository import open_session, run_turn
from tst.db.state_io import load_state, sync_state
from tst.events.context import Kpis, build_prompt
from tst.loader import LoadedData
from tst.sim.dynasty.lifetime import death_chance
from tst.sim.errors import CampaignEndError
from tst.sim.events.director import eligible_targets
from tst.sim.events.models import GameEvent
from tst.sim.research import levels
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

JAN_2040 = 360


@pytest.fixture
def client(tmp_path: Path) -> Iterator[tuple[Client, Path]]:
    save_dir = tmp_path / "saves"
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as raw:
        yield Client(raw), save_dir


def _new(c: Client, name: str, length: str = "standard", **extra: object) -> None:
    body = {"name": name, "seed": 4, "scenario": "funded_spinout", "company_name": "Long Co"}
    c.post("/api/saves", {**body, "campaign_length": length, **extra}, 201)


def _state(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


def _edit(path: Path, change):  # type: ignore[no-untyped-def]
    with open_session(path) as session, session.begin():
        before = load_state(session)
        after = change(before)
        sync_state(session, before, after)
        meta = session.get(SaveMetaRow, 1)
        assert meta is not None
        meta.current_turn = after.turn
    repository._LAST.clear()


def test_the_setting_and_the_campaign_route(client: tuple[Client, Path]) -> None:
    c, _ = client
    _new(c, "std")
    _new(c, "dyn", "dynasty")
    std = c.get("/api/saves/std/campaign")
    assert std["length"] == "standard" and std["end_label"] == "Dec 2039" and std["can_switch"]
    dyn = c.get("/api/saves/dyn/campaign")
    assert dyn["length"] == "dynasty" and dyn["end_label"] == "Dec 2069" and not dyn["can_switch"]
    assert dyn["eras"] == [] and not dyn["dynasty_years"]  # nothing of 2040 shown before it
    out = c.post("/api/saves/std/campaign/continue")
    assert out["campaign"]["length"] == "dynasty"
    c.post("/api/saves/std/campaign/continue", None, 400)  # a one-off


def test_a_standard_campaign_stops_at_december_2039(
    client: tuple[Client, Path], loaded: LoadedData
) -> None:
    c, save_dir = client
    _new(c, "end")
    path = save_dir / "end.tst.sqlite"
    _edit(path, lambda s: replace(s, turn=JAN_2040))
    assert c.get("/api/saves/end/overview")["game_state"] == "campaign_end"
    over = c.get("/api/saves/end/finance/game-over")
    assert over["game_state"] == "campaign_end" and over["can_continue"]
    assert over["ended_label"] == "Dec 2039"
    with pytest.raises(CampaignEndError):
        run_turn(path, loaded)
    err = c.post("/api/saves/end/campaign/end", None)
    assert err["campaign"]["game_state"] == "campaign_end"
    assert _state(path).save_meta.game_state == "campaign_end"
    assert not c.get("/api/saves/end/finance/game-over")["can_continue"]


def test_continuing_at_the_end_plays_on(client: tuple[Client, Path], loaded: LoadedData) -> None:
    c, save_dir = client
    _new(c, "on")
    path = save_dir / "on.tst.sqlite"
    _edit(path, lambda s: replace(s, turn=JAN_2040))
    c.post("/api/saves/on/campaign/continue")
    run_turn(path, loaded)
    state = _state(path)
    assert state.turn == JAN_2040 + 1 and state.save_meta.game_state == "active"
    shown = c.get("/api/saves/on/campaign")
    assert shown["dynasty_years"] and shown["eras"]  # 2040's eras' public windows
    assert all("-" in e["window_label"] for e in shown["eras"])


def _secrets(state: GameState, loaded: LoadedData) -> list[str]:
    """Values that must never be shown: the founder's mortality chance, and the drawn months
    of dynasty eras not yet arrived."""
    b, g = loaded.balance, loaded.game_data
    founder = state.founder_of(state.player.id)
    assert founder is not None
    q = death_chance(state, founder.id, b)
    assert q > 0
    out = [f"{q:.6f}", repr(q)]
    rng = RngFactory(state.save_meta.master_seed)
    for i, era in enumerate(g.eras.eras):
        if era.window and era.window[0][0] >= b.dynasty.start_year:
            if state.era_arrival(era.key) is None:
                t = levels.scheduled_turn(era, i, rng)
                out.append(f'"scheduled_turn": {t}')
    return out


def test_hidden_values_never_in_a_response_or_a_prompt(
    client: tuple[Client, Path], loaded: LoadedData
) -> None:
    c, save_dir = client
    _new(c, "old", "dynasty", founder={"background": "engineer", "age": 60})
    path = save_dir / "old.tst.sqlite"
    _edit(path, lambda s: replace(s, turn=JAN_2040 + 1))  # the founder is 90
    state = _state(path)
    secrets = _secrets(state, loaded)
    bodies = [
        json.dumps(c.get(f"/api/saves/old/{route}"))
        for route in ("campaign", "overview", "finance/game-over", "founder", "family")
    ]
    for body in bodies:
        assert "mortality" not in body and "death_chance" not in body
        assert not any(s in body for s in secrets)
    texts = []
    for template in loaded.game_data.event_templates:
        if template.category != "founder":
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
    assert texts and "mortality" not in joined and not any(s in joined for s in secrets)
