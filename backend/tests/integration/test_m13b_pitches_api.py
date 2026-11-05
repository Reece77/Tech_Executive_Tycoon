"""M13b sub-task 7 through the API and CLI (formulas.md 27.1, 27.6): a pending pitch on the
Executive team panel blocks Continue; approving runs it; the record reaches the profile; the
pitch policy is set; no response carries a hidden value (the Client checks every one)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.integration.test_api_hiring import Client
from tests.integration.test_api_scaleup import BASE, SAVE, api  # noqa: F401
from tst.cli import app as cli_app
from tst.config import get_settings
from tst.db.repository import open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.org import pitches
from tst.sim.state import with_pitch

CPO = 2


def _plant_pitch(path: Path, loaded: LoadedData) -> int:
    """The CPO's best candidate as a pending pitch, as phase 2 would make it."""
    with open_session(path) as session, session.begin():
        before = load_state(session)
        ranked = pitches.candidates(
            before, 1, pitches.SEAT_KINDS["cpo"], 10**9, loaded.balance, loaded.game_data
        )
        pitch = pitches.make_pitch(before, 1, "cpo", CPO, ranked[0], loaded.balance)
        state = with_pitch(replace(before, next_ids=before.next_ids.take("pitch")[1]), pitch)
        sync_state(session, before, state)
    return pitch.id


def test_a_pitch_on_the_panel_blocks_then_runs(
    api: tuple[Client, Path],  # noqa: F811
    loaded: LoadedData,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, path = api
    client.post(f"{BASE}/scaleup/seats/cpo/appoint", {"person_id": CPO})
    out = client.post(f"{BASE}/scaleup/seats/cpo/authority", {"enabled": True})
    cpo = next(s for s in out["scaleup"]["seats"] if s["seat"] == "cpo")
    assert cpo["authority"]["enabled"]
    pitch_id = _plant_pitch(path, loaded)
    out = client.get(f"{BASE}/scaleup")
    (pitch,) = [p for p in out["pitches"] if p["status"] == "pending"]
    assert pitch["pitch_id"] == pitch_id and pitch["kind"] == "new_product"
    assert pitch["case_label"] and pitch["why"] and pitch["cost_cents"] > 0
    assert out["pitch_policy"]["auto_approve_cents"] is None
    assert out["pitch_policy"]["limit_cents"] == out["pitch_policy"]["default_cents"]
    assert client.get(f"{BASE}/events")["blocking_pitch_ids"] == [pitch_id]
    blocked = client.post(f"{BASE}/advance", status=409)
    assert blocked["code"] == "events_open" and blocked["pitch_ids"] == [pitch_id]
    done = client.post(f"{BASE}/scaleup/pitches/{pitch_id}/approve")
    (answered,) = [p for p in done["scaleup"]["pitches"] if p["pitch_id"] == pitch_id]
    assert answered["status"] == "approved"
    with open_session(path) as session:
        state = load_state(session)
    approved = state.pitch(pitch_id)
    assert approved is not None and state.product(approved.target_id) is not None  # type: ignore[arg-type]
    profile = client.get(f"{BASE}/people/{CPO}")
    assert profile["pitch_record"]["pitches"] == 1 and profile["pitch_record"]["approved"] == 1
    client.post(f"{BASE}/scaleup/pitches/{pitch_id}/decline", status=400)  # answered
    policy = client.post(
        f"{BASE}/scaleup/pitch-policy", {"auto_approve_cents": 0, "stop_for_big": True}
    )
    assert policy["scaleup"]["pitch_policy"]["limit_cents"] == 0
    assert policy["scaleup"]["pitch_policy"]["stop_for_big"] is True

    monkeypatch.setenv("TST_SAVE_DIR", str(path.parent))
    get_settings.cache_clear()
    runner = CliRunner()
    listed = runner.invoke(cli_app, ["pitches", "--save", SAVE])
    assert listed.exit_code == 0, listed.output
    assert f"Pitch {pitch_id} [approved]" in listed.output
    assert "auto-approve limit $0.00" in listed.output
    get_settings.cache_clear()
