"""M25 sub-task 3 on saves: achievements are checked after committed turns and actions,
stored once in the profile file, never awarded twice for a replayed check, and never in
Sandbox games or for a scenario win outside scenario mode."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.test_api_hiring import Client
from tests.integration.test_m25_explain import BASE, _copy, played  # noqa: F401 (fixture)
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db import repository
from tst.db.state_io import sync_state
from tst.loader import LoadedData
from tst.profile import store
from tst.profile.check import check
from tst.sim.modes.models import GameMode


def test_launch_earns_its_achievement_once(played: Path, loaded: LoadedData) -> None:  # noqa: F811
    profile = store.load(played.parent)
    first = profile.earned["first_launch"]
    assert first["save"] == "m25" and first["company"] == "Explain Co"
    assert first["date_label"]
    assert "first_customer" in profile.earned
    path = store.profile_path(played.parent)
    before = path.read_bytes()
    assert check(played, loaded) == []  # a replayed check awards nothing twice
    assert path.read_bytes() == before
    raw = json.loads(before)
    assert raw["profile"] == "default" and set(raw["earned"]) == set(profile.earned)


def test_the_api_lists_toasts_and_marks_them_seen(played: Path) -> None:  # noqa: F811
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=played.parent)
    with TestClient(app) as tc:
        api = Client(tc)
        out = api.get(f"{BASE}/achievements")
        assert out["eligible"] and out["reason"] is None
        assert "first_launch" in {a["key"] for a in out["unseen"]}
        hidden = next(a for a in out["achievements"] if a["key"] == "arr_1b")
        assert hidden["title"] == "???" and hidden["description"] == "???"
        assert not hidden["earned"]
        keys = [a["key"] for a in out["unseen"]]
        seen = api.post("/api/profile/achievements/seen", {"keys": keys})
        assert seen["unseen"] == [] and seen["earned"] == out["earned"]
        assert api.get("/api/profile/achievements")["total"] == len(out["achievements"])


def _set_mode(path: Path, mode: GameMode) -> None:
    with repository.open_session(path) as session, session.begin():
        before = repository.load_state(session)
        sync_state(session, before, replace(before, mode=mode))
    repository.forget(path)


def test_sandbox_earns_none_and_scenario_wins_need_scenario_mode(
    played: Path,  # noqa: F811
    loaded: LoadedData,
    tmp_path: Path,
) -> None:
    sandbox = _copy(played, tmp_path / "sandbox")
    _set_mode(sandbox, GameMode(kind="sandbox", scenario="ai_lab", result="success"))
    assert check(sandbox, loaded) == []
    assert store.load(sandbox.parent).earned == {}

    scenario = _copy(played, tmp_path / "scenario")
    _set_mode(scenario, GameMode(kind="scenario", scenario="ai_lab", result="success"))
    found = check(scenario, loaded)
    assert "won_ai_lab" in found and "won_turnaround" not in found
    assert "first_launch" in found  # a fresh profile: everything this save has done
