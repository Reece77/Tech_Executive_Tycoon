"""M51 (formulas.md 63.2-63.3) through the API: challenge rules on a new game, a refused round
with its reason, the Scenarios screen read from the app-wide results file, and a scenario's
verdict kept there after the deadline's month (and replayed with its rules)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.models import SaveMetaRow
from tst.db.repository import open_session, read_session, read_state, replay_save
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.profile import results as kept


@pytest.fixture
def save_dir(tmp_path: Path) -> Path:
    return tmp_path / "saves"


@pytest.fixture
def client(save_dir: Path) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as c:
        yield c


def _create(client: TestClient, **extra: object) -> str:
    body = {"name": "m51", "seed": 5, "scenario": "garage_bootstrap", "company_name": "Kestrel"}
    body.update(extra)
    r = client.post("/api/saves", json=body)
    assert r.status_code == 201, r.text
    return str(r.json()["save_id"])


def test_meta_lists_the_rules_and_the_scenarios(client: TestClient) -> None:
    meta = client.get("/api/meta/new-game").json()
    assert [c["key"] for c in meta["challenges"]] == [
        "bootstrapped", "hardware_only", "no_acquisitions", "one_region", "hard_rivals",
        "no_automation",
    ]  # fmt: skip
    assert len(meta["historical"]) == 11
    cards = client.get("/api/scenarios").json()["scenarios"]
    assert len(cards) == 11 and all(c["best"] is None for c in cards)


def test_a_bootstrapped_campaign_refuses_a_round(client: TestClient, save_dir: Path) -> None:
    save = _create(client, challenges=["bootstrapped"])
    with read_session(save_dir / f"{save}.tst.sqlite") as session:
        state = read_state(session)
    assert state.mode is not None and state.mode.challenges == ("bootstrapped",)
    r = client.post(
        f"/api/saves/{save}/finance/rounds", json={"series": "seed", "target_cents": 100_000_000}
    )
    assert r.status_code == 400
    assert r.json()["code"] == "challenge_refused"
    assert "Bootstrapped" in r.json()["message"]
    over = client.get(f"/api/saves/{save}/finance/game-over").json()
    assert over["challenges"] == ["bootstrapped"]


def test_an_unknown_rule_is_refused(client: TestClient) -> None:
    body = {"name": "x", "seed": 5, "scenario": "garage_bootstrap", "company_name": "K"}
    r = client.post("/api/saves", json={**body, "challenges": ["no_sleep"]})
    assert r.status_code == 400


def test_the_crash_verdict_is_kept_app_wide(
    client: TestClient, save_dir: Path, loaded: LoadedData
) -> None:
    save = _create(client, historical="the_crash", challenges=["one_region"])
    path = save_dir / f"{save}.tst.sqlite"
    with open_session(path) as session, session.begin():  # to December 2009, unplayed
        before = load_state(session)
        sync_state(session, before, replace(before, turn=-1))
        meta = session.get(SaveMetaRow, 1)
        assert meta is not None
        meta.current_turn = -1
    r = client.post(f"/api/saves/{save}/advance")
    assert r.status_code == 200, r.text
    over = client.get(f"/api/saves/{save}/finance/game-over").json()
    assert over["scenario_result"] == "failure"  # no Series A
    score = over["scenario_score"]
    assert score["challenges"] == ["one_region"] and score["score_mult"] == 1.25
    assert over["scenario_best"] is None  # nothing before this save
    stored = kept.load(save_dir)["the_crash"]
    assert len(stored) == 1
    card = next(
        c for c in client.get("/api/scenarios").json()["scenarios"] if c["key"] == "the_crash"
    )
    assert card["played"] == 1 and card["best"]["result"] == "failure"
    assert card["best"]["adjusted"] == round(card["best"]["score"] * 1.25)
    # a new game of the scenario compares with that best
    save2 = _create(client, name="m51b", historical="the_crash")
    assert save2 != save


def test_a_scenario_with_rules_replays(
    client: TestClient, save_dir: Path, loaded: LoadedData
) -> None:
    save = _create(client, historical="the_crash", challenges=["no_acquisitions"])
    path = save_dir / f"{save}.tst.sqlite"
    copy = replay_save(path, save_dir / "copy", "copy", loaded)
    with read_session(path) as a, read_session(copy) as b:
        assert read_state(a).mode == read_state(b).mode
