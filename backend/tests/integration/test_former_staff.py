"""M7c sub-task 1: former staff profiles. Someone who left opens a read-only profile from
every link (the people route answers 404 and the former route answers), built from what the
player knew at departure; planted true values never appear and never move the ranges."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from tests.helpers import make_person, move_save_directors, with_employee
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.models import FormerStaffRow, PersonHiddenRow, PersonSkillRow
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.state import replace

SAVE = "former"
BASE = f"/api/saves/{SAVE}"


@pytest.fixture
def api(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[Client, Path]]:
    save_dir = tmp_path / "saves"
    path = create_save(
        SAVE, 4, "funded_spinout", company_name="Former Co", data=loaded, save_dir=save_dir
    )
    move_save_directors(path)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        state = before
        for pid in (2, 3):
            state = with_employee(loaded, state, make_person(loaded, pid), 9_000_000)
        state = replace(state, next_ids=replace(state.next_ids, person=4))
        sync_state(session, before, state)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client), path


def test_a_fired_employee_opens_a_former_profile(api: tuple[Client, Path]) -> None:
    client, path = api
    shown = client.get(f"{BASE}/people/2")
    client.call("POST", f"{BASE}/people/2/fire")
    client.get(f"{BASE}/people/2", status=404)
    former = client.get(f"{BASE}/people/2/former")
    assert former["name"] == shown["name"] and former["reason"] == "fired"
    assert former["reason_label"] == "Let go" and former["role"] == "software_engineer"
    assert former["tenure_months"] == 0 and former["end_date_label"] == "Jan 2010"
    before = {s["key"]: s["range"] for s in shown["skills"]}
    assert {s["key"]: s["range"] for s in former["skills"]} == before
    assert any(h["person_id"] == 2 for h in former["history"])  # the firing, in History
    client.get(f"{BASE}/people/3/former", status=404)  # still on staff
    client.get(f"{BASE}/people/999/former", status=404)
    with open_session(path) as session:
        row = session.get(FormerStaffRow, 2)
        assert row is not None and row.employment_id > 0


def test_no_former_profile_contains_a_hidden_value(api: tuple[Client, Path]) -> None:
    """Plant unmistakable true values after departure: the profile shows neither them nor
    any change to the ranges the player saw."""
    client, path = api
    client.call("POST", f"{BASE}/people/2/fire")
    first = client.get(f"{BASE}/people/2/former")
    with open_session(path) as session, session.begin():
        session.execute(update(PersonSkillRow).values(value=17.3456))
        session.execute(update(PersonHiddenRow).values(value=19.8765))
    again = client.get(f"{BASE}/people/2/former")
    assert again == first
    blob = json.dumps(again)
    for planted in ("17.3456", "17.35", "19.8765", "19.88", "potential_ability"):
        assert planted not in blob, planted


def test_upgrade_to_0021_backfills_past_departures(api: tuple[Client, Path]) -> None:
    """A save made before M7c: its past departures get a former profile on upgrade."""
    from tst.db import migrate

    client, path = api
    client.call("POST", f"{BASE}/people/2/fire")
    expected = client.get(f"{BASE}/people/2/former")
    client.client.close()
    migrate.downgrade(path, "0020_divisions")
    assert migrate.ensure_current(path) is not None
    with open_session(path) as session:
        row = session.get(FormerStaffRow, 2)
        assert row is not None and row.reason == "fired" and row.employment_id > 0
        ranges = row.knowledge["ranges"]
    assert {s["key"]: [s["range"]["min"], s["range"]["max"]] for s in expected["skills"]} == {
        k: v for k, v in ranges.items() if k in {s["key"] for s in expected["skills"]}
    }
