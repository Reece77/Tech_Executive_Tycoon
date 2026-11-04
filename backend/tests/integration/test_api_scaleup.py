"""M8 API and CLI: divisions, shared services, a product's division, the executive team,
division statements, the support tile, exec-level searches, and the planted-value test for
seat fit and estimates (formulas.md 18.8)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from typer.testing import CliRunner

from tests.helpers import make_person, move_save_directors, play_turn, with_employee
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.cli import app as cli_app
from tst.config import Settings, get_settings
from tst.db.models import PersonSkillRow
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.state import reach_stage, with_company

SAVE = "scale"
BASE = f"/api/saves/{SAVE}"
STAFF = 20


def _build(save_dir: Path, loaded: LoadedData, stage: int = 3) -> Path:
    path = create_save(
        SAVE, 5, "funded_spinout", company_name="Scale Co", data=loaded, save_dir=save_dir
    )
    move_save_directors(path)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        state = before
        for pid in range(2, 2 + STAFF):
            role = "finance_manager" if pid == 21 else "software_engineer"
            state = with_employee(
                loaded, state, make_person(loaded, pid, role, "senior"), 12_000_000
            )
        state = with_company(state, reach_stage(state.player, stage, 0))
        state = replace(state, next_ids=replace(state.next_ids, person=2 + STAFF))
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


def test_divisions_seats_and_statements(api: tuple[Client, Path], loaded: LoadedData) -> None:
    client, path = api
    out = client.get(f"{BASE}/scaleup")
    assert out["in_play"] and out["divisions"] == []
    assert [s["seat"] for s in out["seats"]] == ["coo", "cfo", "cto", "cpo", "cmo", "cro"]
    assert all(s["vacancy_penalty_pct"] is not None for s in out["seats"])
    cto = next(s for s in out["seats"] if s["seat"] == "cto")
    assert cto["vacancy_penalty_pct"] == -5.0
    [pool] = out["support"]
    assert (pool["headcount"], pool["support_staff"], pool["needed"]) == (21, 1, 2)
    org = client.post(f"{BASE}/org/units", {"kind": "division", "name": "Platform"}, 201)["org"]
    assert org["divisions_unlocked"]
    division = next(u for u in org["units"] if u["kind"] == "division")["unit_id"]
    for pid in range(2, 8):
        client.post(f"{BASE}/org/people/{pid}/move", {"unit_id": division})
    client.post(f"{BASE}/org/units/{division}/leader", {"person_id": 2})
    out = client.post(f"{BASE}/scaleup/divisions/{division}/services", {"services": "embedded"})
    [card] = out["scaleup"]["divisions"]
    assert (card["president_id"], card["services"], card["headcount"]) == (2, "embedded", 6)
    assert len(out["scaleup"]["support"]) == 2
    product = client.post(
        f"{BASE}/products", {"name": "Ledger", "category": "fintech", "segments": ["smb"]}, 201
    )["product"]
    assert product["division_id"] is None
    client.post(
        f"{BASE}/scaleup/products/{product['product_id']}/division", {"division_id": division}
    )
    assert client.get(f"{BASE}/products/{product['product_id']}")["division_name"] == "Platform"
    cands = client.get(f"{BASE}/scaleup/seats/cto/candidates")
    president = next(c for c in cands["candidates"] if c["person_id"] == 2)
    assert president["problem"] == "a division president cannot hold a seat"
    assert "exec level" in cands["note"]
    out = client.post(f"{BASE}/scaleup/seats/cto/appoint", {"person_id": 9})
    cto = next(s for s in out["scaleup"]["seats"] if s["seat"] == "cto")
    assert (
        cto["holder_id"] == 9 and cto["fit"].endswith("fit") and cto["vacancy_penalty_pct"] is None
    )
    assert cto["estimated_effect_pct"] is not None
    client.post(f"{BASE}/scaleup/seats/cto/remove")
    client.post(f"{BASE}/scaleup/seats/cto/remove", status=400)
    search = client.post(
        f"{BASE}/recruitment/searches",
        {"role": "software_engineer", "channel": "network", "level": "exec"},
        201,
    )
    assert search["level"] == "exec"
    overview = client.get(f"/api/saves/{SAVE}/overview")
    assert overview["support"]["needed"] >= 1
    play_turn(path, loaded)
    statements = client.get(f"{BASE}/finance/divisions?period=month")
    newest = statements["periods"][0]
    names = [c["name"] for c in newest["columns"]]
    assert names == ["Corporate", "Platform", "Company"]
    corporate, platform, company = newest["columns"]
    assert platform["shared_services_cents"] == 0  # embedded
    assert platform["salaries_benefits_cents"] > 0
    assert (
        corporate["operating_profit_cents"] + platform["operating_profit_cents"]
        == (company["operating_profit_cents"])
    )
    scale = client.get(f"{BASE}/scaleup")
    assert scale["divisions"][0]["operating_profit_cents"] == platform["operating_profit_cents"]


def test_before_stage_3(tmp_path: Path, loaded: LoadedData) -> None:
    save_dir = tmp_path / "saves"
    _build(save_dir, loaded, stage=2)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as raw:
        client = Client(raw)
        out = client.get(f"{BASE}/scaleup")
        assert not out["in_play"] and out["support"] == []
        assert all(s["vacancy_penalty_pct"] is None for s in out["seats"])
        assert client.get(f"/api/saves/{SAVE}/overview")["support"] is None
        client.post(f"{BASE}/scaleup/seats/cto/appoint", {"person_id": 3}, status=400)


def test_no_scaleup_response_contains_a_true_seat_score(
    api: tuple[Client, Path], loaded: LoadedData
) -> None:
    """Plant true skills that give s = 17.3456 and e = 0.918; the API shows only fit words and
    estimates from the displayed ranges, never s or e."""
    client, path = api
    with open_session(path) as session, session.begin():
        session.execute(update(PersonSkillRow).values(value=17.3456))
    client.post(f"{BASE}/scaleup/seats/cfo/appoint", {"person_id": 5})
    blobs = [
        json.dumps(client.get(f"{BASE}/scaleup")),
        json.dumps(client.get(f"{BASE}/scaleup/seats/cto/candidates")),
        json.dumps(client.get(f"/api/saves/{SAVE}/overview")),
    ]
    blob = "\n".join(blobs)
    for planted in ("17.3456", "17.35", "0.918", "0.9182", "9.18"):
        assert planted not in blob, planted


def test_cli_divisions_execs_and_appoint(
    tmp_path: Path, loaded: LoadedData, monkeypatch: Any
) -> None:
    save_dir = tmp_path / "saves"
    _build(save_dir, loaded)
    monkeypatch.setenv("TST_SAVE_DIR", str(save_dir))
    runner = CliRunner()
    out = runner.invoke(cli_app, ["divisions", "--save", SAVE])
    assert out.exit_code == 0, out.output
    assert "No divisions yet" in out.output and "One support person per 15 staff" in out.output
    out = runner.invoke(cli_app, ["appoint", "--save", SAVE, "--seat", "cto", "--person", "3"])
    assert out.exit_code == 0, out.output
    assert "is now CTO" in out.output
    out = runner.invoke(cli_app, ["execs", "--save", SAVE])
    assert out.exit_code == 0, out.output
    assert "CTO" in out.output and "est." in out.output and "vacant" in out.output


# --- M8r finding 4: seat-derived numbers come from displayed estimates (18.8) ---------------

COO_ID = 5


def _same_range_values(
    loaded: LoadedData, path: Path, skill: str, person_id: int = COO_ID
) -> tuple[float, float]:
    """Two true values of the person's (the COO's) `skill`, as far apart as possible, that
    the company sees as the same displayed range."""
    from tst.sim.people.reveal import revealed_range

    with open_session(path) as session:
        state = load_state(session)
    person, reveal = state.person(person_id), state.reveal(1, person_id)
    assert reveal is not None

    def shown(v: float) -> tuple[int, int]:
        return revealed_range(
            replace(person, skills=person.skills.updated({skill: v})), reveal, skill
        )

    start = person.skills[skill]
    same = [v / 100 for v in range(round(start * 100) - 150, round(start * 100) + 151)]
    same = [v for v in same if 1 <= v <= 20 and shown(v) == shown(start)]
    return min(same), max(same)


def _plant(path: Path, values: dict[str, float], person_id: int = COO_ID) -> None:
    with open_session(path) as session, session.begin():
        for skill, value in values.items():
            session.execute(
                update(PersonSkillRow)
                .where(PersonSkillRow.person_id == person_id, PersonSkillRow.skill == skill)
                .values(value=value)
            )


def _screens(client: Client, product_id: int) -> str:
    return json.dumps(
        {
            "scaleup": client.get(f"{BASE}/scaleup"),
            "org": client.get(f"{BASE}/org"),
            "overview": client.get(f"/api/saves/{SAVE}/overview"),
            "product": client.get(f"{BASE}/products/{product_id}"),
            "portfolio": client.get(f"{BASE}/portfolio"),
            "person": client.get(f"{BASE}/people/{COO_ID}"),
            "research": client.get(f"{BASE}/research"),  # M12r finding 2
        },
        sort_keys=True,
    )


def test_hidden_coo_skill_changes_no_response(api: tuple[Client, Path], loaded: LoadedData) -> None:
    """An occupied COO, a deep division (depth-3 teams pay the layer tax) and an under-covered
    pool (21 staff, 1 support): two COOs the player sees identically give identical screens."""
    client, path = api
    org = client.post(f"{BASE}/org/units", {"kind": "division", "name": "Platform"}, 201)["org"]
    division = next(u for u in org["units"] if u["kind"] == "division")["unit_id"]
    org = client.post(
        f"{BASE}/org/units", {"kind": "department", "name": "Eng", "parent_id": division}, 201
    )["org"]
    dept = next(u for u in org["units"] if u["kind"] == "department")["unit_id"]
    org = client.post(
        f"{BASE}/org/units", {"kind": "team", "name": "Core", "parent_id": dept}, 201
    )["org"]
    team = next(u for u in org["units"] if u["kind"] == "team")["unit_id"]
    for pid in range(10, 16):
        client.post(f"{BASE}/org/people/{pid}/move", {"unit_id": team})
    product = client.post(
        f"{BASE}/products", {"name": "Ledger", "category": "b2b_saas", "segments": ["smb"]}, 201
    )["product"]["product_id"]
    client.post(f"{BASE}/products/{product}/assign", {"unit_id": team})
    lab = _research_team(client, dept, range(16, 19))  # M12r: a deep research team too
    client.post(f"{BASE}/people/21/fire")  # the finance manager: 21 staff, the COO alone
    client.post(f"{BASE}/scaleup/seats/coo/appoint", {"person_id": COO_ID})
    weights = loaded.balance.exec_seats.seats["coo"].weights
    lows, highs = {}, {}
    for skill in weights:
        lows[skill], highs[skill] = _same_range_values(loaded, path, skill)
    assert sum(w * (highs[s] - lows[s]) for s, w in weights.items()) > 0.5  # true s differs

    _plant(path, lows)
    weak = _screens(client, product)
    _plant(path, highs)
    strong = _screens(client, product)
    scale = json.loads(strong)["scaleup"]
    assert any(p["output_effect_pct"] < 0 for p in scale["support"])  # an under-covered pool
    assert any("layer tax" in d["effect_note"] for d in scale["divisions"])  # a deep division
    [project] = json.loads(strong)["research"]["projects"]
    assert project["unit_id"] == lab and project["gain_per_month"] > 0
    assert weak == strong


def _research_team(client: Client, parent: int | None, people: range) -> int:
    """A team under `parent` with `people`, researching the software platform."""
    body: dict[str, Any] = {"kind": "team", "name": "Lab"}
    if parent is not None:
        body["parent_id"] = parent
    org = client.post(f"{BASE}/org/units", body, 201)["org"]
    unit = next(u for u in org["units"] if u["name"] == "Lab")["unit_id"]
    for pid in people:
        client.post(f"{BASE}/org/people/{pid}/move", {"unit_id": unit})
    client.post(f"{BASE}/research/projects", {"unit_id": unit, "domain": "software_platform"})
    return int(unit)


CTO_ID = 9


def test_hidden_cto_skill_changes_no_research_response(
    api: tuple[Client, Path], loaded: LoadedData
) -> None:
    """M12r finding 2 (Codex review 3): two CTOs the player sees identically give a
    byte-identical Research screen, gain_per_month and months_to_era included (18.8, 21.7)."""
    client, path = api
    lab = _research_team(client, None, range(10, 16))
    client.post(f"{BASE}/scaleup/seats/cto/appoint", {"person_id": CTO_ID})
    weights = loaded.balance.exec_seats.seats["cto"].weights
    lows, highs = {}, {}
    for skill in weights:
        lows[skill], highs[skill] = _same_range_values(loaded, path, skill, CTO_ID)
    assert sum(w * (highs[s] - lows[s]) for s, w in weights.items()) > 0.5  # true s differs

    _plant(path, lows, CTO_ID)
    weak = client.client.get(f"{BASE}/research")
    _plant(path, highs, CTO_ID)
    strong = client.client.get(f"{BASE}/research")
    [project] = strong.json()["projects"]
    assert project["unit_id"] == lab and project["gain_per_month"] > 0
    assert project["months_to_era"] is not None
    assert weak.text == strong.text
