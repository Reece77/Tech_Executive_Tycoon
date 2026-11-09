"""M21 API (formulas.md 38): the Fabs screen, the node timeline and the fab actions on fixture
saves (tools/e2e_m21_save.py); the hidden overrun and future nodes' months kept out of
responses; fabs' records through persistence."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api import find_forbidden_keys
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.repository import load_state, open_session
from tst.loader import LoadedData
from tst.sim.fabs import market as fm

TOOLS = Path(__file__).resolve().parents[3] / "tools"
BASE = "/api/saves/{}"


def _tools() -> Any:
    sys.path.insert(0, str(TOOLS))
    import e2e_m21_save

    return e2e_m21_save


@pytest.fixture
def saves(tmp_path: Path) -> Path:
    return tmp_path / "saves"


@pytest.fixture
def api(saves: Path) -> Iterator[Client]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as client:
        yield Client(client)


def test_the_node_timeline_shows_history_and_hides_future_months(
    api: Client, saves: Path, loaded: LoadedData
) -> None:
    _tools().nodes(saves, "n", loaded)
    out = api.get(f"{BASE.format('n')}/nodes")
    assert find_forbidden_keys(out) == []
    by = {n["key"]: n for n in out["nodes"]}
    n5 = by["n5"]
    assert n5["arrived"] and n5["first_label"] == "Apr 2020"
    assert any(r["name"] == "TSMC" and r["label"] == "Apr 2020" for r in n5["reached"])
    assert out["leading"] == "n5"
    assert not by["n3"]["arrived"] and by["n3"]["first_label"] == "Jun 2022"  # history is public
    a16 = by["a16"]
    assert not a16["arrived"] and a16["first_turn"] is None and a16["reached"] == []
    assert a16["window_label"] == "expected 2026-2027" and a16["capital_cents"] is None
    with open_session(saves / "n.tst.sqlite") as session:
        state = load_state(session)
    tl = fm.timeline(state, loaded.balance, loaded.game_data)
    drawn = tl.arrival["a16"]
    assert str(drawn) not in json.dumps(a16)  # the drawn month never leaves the engine
    names = {f["name"] for f in out["foundries"]}
    assert {"TSMC", "Samsung Foundry", "Intel", "GlobalFoundries", "UMC", "SMIC"} <= names


def test_build_a_fab_shows_the_estimate_not_the_overrun(
    api: Client, saves: Path, loaded: LoadedData
) -> None:
    _tools().euv(saves, "e", loaded)
    base = BASE.format("e")
    q = api.get(f"{base}/fabs/quote?node=n5&region=east_asia&size=100000")
    assert q["allowed"] and q["euv"] and q["tools"] == 50 and q["tools_label"]
    out = api.post(f"{base}/fabs/build", json={"node": "n5", "region": "east_asia", "size": 100000})
    assert find_forbidden_keys(out) == []
    fab = out["fabs"]["fabs"][0]
    assert fab["status"] == "building" and fab["estimate_cents"] == q["capex_cents"]
    with open_session(saves / "e.tst.sqlite") as session:
        state = load_state(session)
    facility = state.facility(fab["id"])
    assert facility is not None and facility.capex_cents != fab["estimate_cents"]
    assert str(facility.capex_cents) not in json.dumps(out)
    got = fm.fab_of(state, fab["id"])
    assert got is not None and got.tools == 50 and got.node == "n5"  # persisted
    # a node the research does not reach is refused with its reason
    bad = api.client.post(
        f"{base}/fabs/build", json={"node": "a16", "region": "east_asia", "size": 10000}
    )
    assert bad.status_code >= 400


def test_a_live_fab_sells_slots_and_its_yield_climbs(
    api: Client, saves: Path, loaded: LoadedData
) -> None:
    _tools().mature(saves, "m", loaded)
    base = BASE.format("m")
    before = api.get(f"{base}/fabs")["fabs"][0]
    assert before["node"] == "n28"
    api.post(f"{base}/advance")
    first = api.get(f"{base}/fabs")["fabs"][0]
    assert first["status"] == "live" and first["month"]["sold"] > 0
    assert first["customers"] and first["month"]["revenue_cents"] > 0
    api.post(f"{base}/advance")
    second = api.get(f"{base}/fabs")["fabs"][0]
    assert second["yield"] > first["yield"]
    assert second["history"] and find_forbidden_keys(second) == []
