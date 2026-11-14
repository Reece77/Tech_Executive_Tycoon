"""M36 API (formulas.md 45.9): a new game with a family, the Family screen and its actions
through the persistence path; succession survives a cold reload; and the hidden-value test:
no family member's potential or hidden trait reaches a response or an LLM prompt."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db import repository
from tst.db.repository import open_session, run_turn
from tst.db.state_io import load_state, sync_state
from tst.events.context import Kpis, build_prompt
from tst.loader import LoadedData
from tst.sim.events.director import eligible_targets
from tst.sim.events.models import GameEvent
from tst.sim.family import rules
from tst.sim.founder import personal
from tst.sim.people.models import HiddenTraits
from tst.sim.state import GameState, family_member, life_of, with_family_member, with_person

SAVE = "fam"
BASE = f"/api/saves/{SAVE}"
PLANTED_PA = 123.456789  # unmistakable hidden values
PLANTED_TRAIT = 17.654321


@pytest.fixture
def api(tmp_path: Path) -> Iterator[tuple[Client, Path]]:
    save_dir = tmp_path / "saves"
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        c = Client(client)
        c.post(
            "/api/saves",
            {
                "name": SAVE,
                "seed": 8,
                "scenario": "funded_spinout",
                "company_name": "Dynasty Co",
                "founder": {"background": "engineer", "age": 60},
                "family": {"setting": "children", "child_ages": [30, 26]},
            },
            201,
        )
        yield c, save_dir / f"{SAVE}.tst.sqlite"


def _state(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


def _edit(path: Path, change):  # type: ignore[no-untyped-def]
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, change(before))
    repository._LAST.clear()


def test_family_screen(api: tuple[Client, Path]) -> None:
    client, _ = api
    out = client.get(f"{BASE}/family")
    assert out["exists"] and out["setting"] == "children"
    assert out["partner"] is not None and len(out["children"]) == 2
    kid = out["children"][0]
    assert kid["age"] == 30 and kid["skills"][0]["range"]["min"] <= kid["skills"][0]["range"]["max"]
    assert isinstance(kid["potential"], str)
    assert out["estate"]["region"] == "north_america" and out["dynasty"]["total"] is not None
    res = client.post(f"{BASE}/family/time", {"energy": 14})
    assert res["family"]["family_time"] == 14


def test_family_none_has_no_family(tmp_path: Path) -> None:
    save_dir = tmp_path / "saves"
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as raw:
        c = Client(raw)
        c.post("/api/saves", {"name": "solo", "seed": 1, "scenario": "funded_spinout",
                              "company_name": "Solo"}, 201)  # fmt: skip
        out = c.get("/api/saves/solo/family")
        assert not out["exists"] and out["children"] == []
        err = c.post("/api/saves/solo/family/time", {"energy": 5}, 400)
        assert "no family" in err["message"]


def _join(path: Path, loaded: LoadedData) -> list[int]:
    def change(state: GameState) -> GameState:
        for m in rules.children(state):
            state = with_family_member(state, replace(m, closeness=95.0))
        return state

    _edit(path, change)
    return [m.person_id for m in rules.children(_state(path))]


def test_succession_survives_a_cold_reload(api: tuple[Client, Path], loaded: LoadedData) -> None:
    client, path = api
    os.environ["TST_STATE_CACHE_CHECK"] = "1"
    try:
        kids = _join(path, loaded)
        state = _state(path)
        heir = kids[0]
        person = state.person(heir)
        role = next(
            r.key
            for r in loaded.game_data.roles
            if r.founder_fit and rules.roles_match(person, r.key, loaded.game_data)
        )
        client.post(
            f"{BASE}/family/job",
            {"person_id": heir, "company_id": 1, "role": role, "level": "senior"},
        )
        run_turn(path, loaded)
        old = _state(path).founder_of(1)
        assert old is not None
        out = client.post(f"{BASE}/family/succession", {"heir_id": heir})
        assert out["family"]["head_id"] == heir and out["family"]["adviser"]["person_id"] == old.id
        repository._LAST.clear()  # cold
        cold = _state(path)
        founder = cold.founder_of(1)
        assert founder is not None and founder.id == heir
        life = life_of(cold, heir)
        assert life is not None and life.stress == loaded.balance.family.heir_stress
        assert any(s.person_id == old.id for s in cold.board(1))
        assert not cold.person(old.id).is_founder
        run_turn(path, loaded)  # the heir plays on; the remembered state matches the save
        assert _state(path).founder_of(1).id == heir  # type: ignore[union-attr]
    finally:
        os.environ.pop("TST_STATE_CACHE_CHECK", None)


def _plant(state: GameState) -> GameState:
    for m in state.family_members:
        p = state.person(m.person_id)
        hidden = HiddenTraits(tuple((k, PLANTED_TRAIT) for k, _ in p.hidden.items))
        state = with_person(state, replace(p, potential_ability=PLANTED_PA, hidden=hidden))
    return personal.credit(state, state.family.head_id, 10**9, "secondary")  # type: ignore[union-attr]


def _planted(text: str) -> bool:
    return any(s in text for s in ("123.45", "17.65", "potential_ability", "burnout_risk"))


def test_hidden_values_never_in_a_response(api: tuple[Client, Path]) -> None:
    client, path = api
    _edit(path, _plant)
    state = _state(path)
    assert family_member(state, rules.children(state)[0].person_id) is not None
    body = json.dumps(client.get(f"{BASE}/family"))
    assert not _planted(body)
    for m in state.family_members:
        assert not _planted(client.client.get(f"{BASE}/people/{m.person_id}").text)


def test_hidden_values_never_in_a_prompt(api: tuple[Client, Path], loaded: LoadedData) -> None:
    _, path = api
    _edit(path, _plant)
    state = _state(path)
    kid = rules.children(state)[0].person_id
    texts = []
    for template in loaded.game_data.event_templates:
        if not template.id.startswith("family_"):
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
            person_ids=(kid,),
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
    assert len(texts) >= 8 and not _planted("\n".join(texts))
