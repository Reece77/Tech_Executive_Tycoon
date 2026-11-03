"""M11 API: the Research screen, projects, licences, the era timeline, and the planted-value
test for rivals' exact leads (formulas.md 21.7)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.helpers import make_person, move_save_directors, play_turn, with_employee
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.org.models import OrgUnit
from tst.sim.research.models import ResearchLead
from tst.sim.state import with_employment, with_unit

SAVE = "lab"
BASE = f"/api/saves/{SAVE}"
IBM = 17


def _build(save_dir: Path, loaded: LoadedData) -> Path:
    path = create_save(
        SAVE, 5, "funded_spinout", company_name="Kestrel", data=loaded, save_dir=save_dir
    )
    move_save_directors(path)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        state = before
        unit_id, ids = state.next_ids.take("unit")
        state = with_unit(
            replace(state, next_ids=ids),
            OrgUnit(unit_id, 1, "team", "AI lab", None, None, "office", created_turn=0),
        )
        for pid in range(2, 8):
            state = with_employee(
                loaded, state, make_person(loaded, pid, "data_scientist", "senior"), 12_000_000
            )
            employment = state.employment_of(pid)
            assert employment is not None
            state = with_employment(state, replace(employment, unit_id=unit_id))
        state = replace(state, next_ids=replace(state.next_ids, person=8))
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


def _plant(path: Path, *leads: ResearchLead) -> None:
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, replace(before, research_leads=leads))


def test_research_screen_and_a_project(api: tuple[Client, Path], loaded: LoadedData) -> None:
    client, path = api
    out = client.get(f"{BASE}/research")
    assert [d["key"] for d in out["domains"]] == [
        "software_platform",
        "ai",
        "infrastructure",
        "chip_design",
        "devices",
    ]
    ai = next(d for d in out["domains"] if d["key"] == "ai")
    assert (ai["baseline"], ai["lead"], ai["next_era"]) == (10.0, 0.0, "Deep learning")
    [unit] = out["units"]
    assert (unit["name"], unit["researchers"]) == ("AI lab", 6)
    eras = client.get(f"{BASE}/eras")
    assert [e["status"] for e in eras][:2] == ["next", "next"]
    assert all(e["arrived"] is None for e in eras)
    started = client.post(f"{BASE}/research/projects", {"unit_id": unit["unit_id"], "domain": "ai"})
    [project] = started["research"]["projects"]
    assert project["researchers"] == 6 and project["funded_pct"] == 100.0
    assert project["gain_per_month"] > 0 and project["next_era"] == "Deep learning"
    assert started["research"]["units"] == []
    play_turn(path, loaded)
    after = client.get(f"{BASE}/research")
    assert next(d for d in after["domains"] if d["key"] == "ai")["lead"] > 0
    assert after["projects"][0]["last_month_gain"] > 0
    budget = client.post(
        f"{BASE}/research/projects/{project['project_id']}/budget", {"budget_cents": 0}
    )
    assert budget["research"]["projects"][0]["funded_pct"] == 0.0
    stopped = client.post(f"{BASE}/research/projects/{project['project_id']}/stop")
    assert stopped["research"]["projects"] == [] and len(stopped["research"]["units"]) == 1


def test_license_in_from_a_rival(api: tuple[Client, Path]) -> None:
    client, path = api
    _plant(path, ResearchLead(IBM, "devices", 40.0))
    out = client.get(f"{BASE}/research")
    devices = next(r for r in out["rivals"] if r["domain"] == "devices")
    ibm = next(r for r in devices["rivals"] if r["company_id"] == IBM)
    assert ibm["low"] <= 40 <= ibm["high"] and ibm["can_license_in"]
    assert 0 < ibm["max_points"] <= 30
    done = client.post(
        f"{BASE}/research/licenses/in",
        {"company_id": IBM, "domain": "devices", "points": 5},
    )
    level = next(d for d in done["research"]["domains"] if d["key"] == "devices")
    assert level["lead"] == 5.0
    [licence] = done["research"]["licenses"]
    assert licence["direction"] == "in" and licence["company"] == "IBM"
    narrowed = next(
        r
        for r in next(r for r in done["research"]["rivals"] if r["domain"] == "devices")["rivals"]
        if r["company_id"] == IBM
    )
    assert narrowed["licensed"] and narrowed["high"] - narrowed["low"] <= 5
    client.post(
        f"{BASE}/research/licenses/in",
        {"company_id": IBM, "domain": "devices", "points": 26},
        status=400,
    )


def test_no_response_shows_a_rivals_exact_lead(api: tuple[Client, Path]) -> None:
    """Plant a rival lead of 23.4567 in AI; every research, era, competitor and overview
    response shows ranges only (21.7)."""
    client, path = api
    _plant(path, ResearchLead(IBM, "ai", 23.4567), ResearchLead(IBM, "devices", 31.789))
    blobs = [
        json.dumps(client.get(f"{BASE}/research")),
        json.dumps(client.get(f"{BASE}/eras")),
        json.dumps(client.get(f"{BASE}/rivals")),
        json.dumps(client.get(f"{BASE}/overview")),
        json.dumps(client.get(f"{BASE}/rivals/{IBM}")),
    ]
    blob = "\n".join(blobs)
    for planted in ("23.4567", "23.46", "23.5", "31.789", "31.79", "31.8"):
        assert planted not in blob, planted
    out = json.loads(blobs[0])
    ai = next(r for r in out["rivals"] if r["domain"] == "ai")
    ibm = next(r for r in ai["rivals"] if r["company_id"] == IBM)
    assert ibm["low"] <= 23.4567 <= ibm["high"]
    assert ibm["low"] + ibm["high"] != round(2 * 23.4567)
