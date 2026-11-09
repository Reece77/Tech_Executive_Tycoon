"""M22 API (formulas.md 39): the World screen and its actions on fixture saves
(tools/e2e_m22_save.py); no rule before its announcement and no seeded escalation ahead of its
month reach a response; licences, variants and the gallium ban through persistence."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api import find_forbidden_keys
from tests.integration.test_api_hiring import Client
from tst.api import geopolitics_views
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.repository import load_state, open_session
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn

TOOLS = Path(__file__).resolve().parents[3] / "tools"
BASE = "/api/saves/{}"


def _tools() -> Any:
    sys.path.insert(0, str(TOOLS))
    import e2e_m22_save

    return e2e_m22_save


@pytest.fixture
def saves(tmp_path: Path) -> Path:
    return tmp_path / "saves"


@pytest.fixture
def api(saves: Path) -> Iterator[Client]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as client:
        yield Client(client)


def test_october_2022_rules_and_a_compliant_variant(
    api: Client, saves: Path, loaded: LoadedData
) -> None:
    _tools().chips(saves, "c", loaded)
    base = BASE.format("c")
    w = api.get(f"{base}/world")
    assert find_forbidden_keys(w) == []
    rules = {r["key"]: r for r in w["rules"]}
    assert rules["us_oct_2022"]["status"] == "in_force"
    assert "us_oct_2023" not in rules  # not announced yet
    assert not any(r["seeded"] for r in w["rules"])
    assert w["tension"] == 75
    [p] = w["products"]
    assert p["restricted"] == ["china"] and p["licensable"] == ["china"]
    assert p["regions"] == [{"region": "east_asia", "blocked": pytest.approx(0.55), "variant": 0}]
    out = api.post(f"{base}/world/variant", json={"product_id": p["product_id"]})
    [after] = out["world"]["products"]
    assert after["has_variant"] and after["regions"][0]["variant"] > 0
    out = api.post(
        f"{base}/world/licence", json={"product_id": p["product_id"], "country": "china"}
    )
    [lic] = out["world"]["licences"]
    assert lic["status"] == "pending" and "chance" not in lic
    with open_session(saves / "c.tst.sqlite") as session:
        state = load_state(session)
    assert state.variants and state.licences  # persisted


def test_no_rule_reaches_the_api_before_its_announcement(saves: Path, loaded: LoadedData) -> None:
    path = _tools().chips(saves, "h", loaded)
    with open_session(path) as session:
        state = load_state(session)
    for year, month in ((2022, 9), (2023, 2), (2024, 11)):
        turn = ym_to_turn(year, month)
        w = geopolitics_views.world_out(replace(state, turn=turn), loaded)
        assert loaded.game_data.controls is not None
        for r in w.rules:
            rule = loaded.game_data.controls.rule(r.key)
            assert rule.announced_turn <= turn, r.key
        assert all(t.turn <= turn for t in w.tension_history)


def test_the_gallium_ban_raises_the_premium(api: Client, saves: Path, loaded: LoadedData) -> None:
    _tools().gallium(saves, "g", loaded)
    base = BASE.format("g")
    api.post(f"{base}/advance")  # November 2024 played; December's ban is in force
    w = api.get(f"{base}/world")
    [ga] = [x for x in w["supply"] if x["good"] == "gallium"]
    assert ga["exposed"] > 0.9 and ga["allocation"] < 0.1
    assert ga["price_premium"] == pytest.approx(ga["exposed"] * 0.6)
    assert {r["key"] for r in w["rules"] if r["status"] == "in_force"} >= {"cn_ga_ge_us_ban_2024"}
