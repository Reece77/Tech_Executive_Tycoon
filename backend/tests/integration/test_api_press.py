"""M14b API: press, promises and credibility; the rival leader panel; Replace; and the
hidden-value tests (29.6): leadership fit never shows true skills, and no response carries a
backfire before it happens."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from tests.helpers import make_person, move_save_directors, with_employee
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.models import PersonSkillRow
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.press.models import PressMoment
from tst.sim.state import with_employment, with_press_moment

SAVE = "press"
BASE = f"/api/saves/{SAVE}"


def _build(save_dir: Path, loaded: LoadedData) -> Path:
    path = create_save(
        SAVE, 5, "funded_spinout", company_name="Kestrel", data=loaded, save_dir=save_dir
    )
    move_save_directors(path)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        engineer = make_person(loaded, 2, "software_engineer", "senior")
        state = with_employee(loaded, before, engineer, 10**7)
        state = with_employee(loaded, state, make_person(loaded, 3, "recruiter", "mid"), 8 * 10**6)
        state = replace(state, next_ids=replace(state.next_ids, person=4))
        sync_state(session, before, state)
    return path


@pytest.fixture
def api(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[Client, Path]]:
    save_dir = tmp_path / "saves"
    path = _build(save_dir, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client), path


def _edit(path: Path, change):  # type: ignore[no-untyped-def]
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, change(before))


def test_press_panel_and_a_promise(api: tuple[Client, Path], loaded: LoadedData) -> None:
    client, path = api
    out = client.get(f"{BASE}/press")
    assert out["credibility"]["value"] == 50 and out["promises"] == []
    assert out["form"]["moment_id"] is None
    client.post(f"{BASE}/press/promises", {"promise": "no_layoffs"}, status=400)

    def answered(state):  # type: ignore[no-untyped-def]
        m = PressMoment(
            1,
            1,
            "launch",
            state.turn,
            "answered",
            state.turn,
            tone="bold",
            answered_turn=state.turn,
        )
        ids = replace(state.next_ids, press_moment=2)
        return with_press_moment(replace(state, next_ids=ids), m)

    _edit(path, answered)
    out = client.get(f"{BASE}/press")
    assert out["form"]["moment_id"] == 1
    made = client.post(f"{BASE}/press/promises", {"promise": "no_layoffs"})["press"]
    (p,) = made["promises"]
    assert p["status"] == "open" and "no layoffs" in p["words"] and p["months_left"] == 12
    client.post(f"{BASE}/press/promises", {"promise": "no_layoffs"}, status=400)  # one a moment
    blob = json.dumps(made)
    for hidden in ("share_bp", "backfired", "ambition"):
        assert f'"{hidden}"' not in blob, hidden


def test_rival_leader_and_feuds(api: tuple[Client, Path]) -> None:
    client, _ = api
    rid = client.get(f"{BASE}/rivals")["rivals"][0]["company_id"]
    out = client.get(f"{BASE}/rivals/{rid}/leader")
    assert out["ceo"] and out["feud"]["score"] == 0 and not out["feud"]["rivalry"]
    assert client.get(f"{BASE}/feuds") == []


def test_replace_flow(api: tuple[Client, Path]) -> None:
    client, path = api
    assert client.get(f"{BASE}/recruitment/replaceable") == []

    def resign(state):  # type: ignore[no-untyped-def]
        e = state.employment_of(2)
        notice = replace(e, status="notice", end_turn=state.turn + 1, end_reason="resigned")
        return with_employment(state, notice)

    _edit(path, resign)
    (row,) = client.get(f"{BASE}/recruitment/replaceable")
    assert row["person_id"] == 2 and row["can_replace"] and row["reason"] == "resigned"
    client.post(f"{BASE}/recruitment/replace", {"person_id": 2})
    (row,) = client.get(f"{BASE}/recruitment/replaceable")
    assert not row["can_replace"] and "already" in row["problem"]


def test_leadership_fit_never_shows_true_skills(api: tuple[Client, Path]) -> None:
    """Plant distinctive true skills and find only star ranges in People and Org."""
    client, path = api
    with open_session(path) as session, session.begin():
        session.execute(
            update(PersonSkillRow)
            .where(PersonSkillRow.person_id == 2)
            .where(PersonSkillRow.skill.in_(("leadership", "mentoring", "communication")))
            .values(value=17.3456)
        )
    people = client.get(f"{BASE}/people")
    org = client.get(f"{BASE}/org")
    blob = json.dumps(people) + json.dumps(org)
    for planted in ("17.3456", "17.35", "17.346"):
        assert planted not in blob, planted
    person = next(r for r in people if r["person_id"] == 2)
    assert 1 <= person["leadership_fit_low"] <= person["leadership_fit_high"] <= 5
