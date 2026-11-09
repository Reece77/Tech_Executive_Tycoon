"""M20 API (formulas.md 36): the Refineries screen and its actions on fixture saves
(tools/e2e_m20_save.py), the hidden overrun kept out of responses, and refining's records
through persistence."""

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

TOOLS = Path(__file__).resolve().parents[3] / "tools"
BASE = "/api/saves/{}"


def _tools() -> Any:
    sys.path.insert(0, str(TOOLS))
    import e2e_m20_save

    return e2e_m20_save


@pytest.fixture
def saves(tmp_path: Path) -> Path:
    return tmp_path / "saves"


@pytest.fixture
def api(saves: Path) -> Iterator[Client]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as client:
        yield Client(client)


def test_build_a_smelter_where_power_is_cheap(api: Client, saves: Path, loaded: LoadedData) -> None:
    _tools().smelter(saves, "s", loaded)
    base = BASE.format("s")
    screen = api.get(f"{base}/refineries")
    assert screen["plants"] == [] and find_forbidden_keys(screen) == []
    assert {r["key"] for r in screen["recipes"]} == set(loaded.balance.refining.recipes)
    q = "recipe=silicon_smelter&size=10000"
    cheap = api.get(f"{base}/refineries/quote?{q}&region=south_southeast_asia")
    europe = api.get(f"{base}/refineries/quote?{q}&region=europe")
    assert cheap["unit_cost_cents"] < europe["unit_cost_cents"]
    assert europe["power_cents"] - cheap["power_cents"] == pytest.approx(12 * 6800 * 0.65)
    out = api.post(
        f"{base}/refineries/build",
        json={"recipe": "silicon_smelter", "region": "south_southeast_asia", "size": 10000},
    )
    plant = out["refineries"]["plants"][0]
    assert plant["status"] == "building" and plant["estimate_cents"] == cheap["capex_cents"]
    assert find_forbidden_keys(out) == []
    with open_session(saves / "s.tst.sqlite") as session:
        state = load_state(session)
    facility = state.facility(plant["id"])
    assert facility is not None
    true_capex = facility.capex_cents  # carries the hidden overrun
    assert true_capex != plant["estimate_cents"]
    assert str(true_capex) not in json.dumps(out)
    api.post(
        f"{base}/refineries/build",
        json={"recipe": "silicon_smelter", "region": "europe", "size": 12345},
        status=400,
    )


def test_a_wafer_plant_supplies_the_groups_chips(
    api: Client, saves: Path, loaded: LoadedData
) -> None:
    path = _tools().wafers(saves, "w", loaded)
    base = BASE.format("w")
    api.post(f"{base}/advance")
    screen = api.get(f"{base}/refineries")
    plant = screen["plants"][0]
    assert plant["month"]["to_group"] > 0 and plant["month"]["to_spot"] > 0
    supply = screen["supply"][0]
    assert supply["good"] == "silicon_wafer" and supply["product"] == "Forge SoC"
    assert supply["unit_cents"] < supply["market_cents"]
    stages = {link["stage"] for link in screen["chain"]}
    assert {"wafer", "chip", "device"} <= stages
    wafer = next(link for link in screen["chain"] if link["stage"] == "wafer")
    assert "Forge SoC" in wafer["supplies"]
    with open_session(path) as session:  # refining's records round-trip
        state = load_state(session)
    assert state.refineries[0].month is not None
    assert state.refineries[0].month.to_group == pytest.approx(plant["month"]["to_group"])
    assert state.own_supply and state.own_supply[0].product_id is not None


def test_a_power_curb_shows_on_the_plant(api: Client, saves: Path, loaded: LoadedData) -> None:
    _tools().curb(saves, "c", loaded)
    base = BASE.format("c")
    api.post(f"{base}/advance")
    plant = api.get(f"{base}/refineries")["plants"][0]
    assert plant["curbed_until"] == "Oct 2021" and plant["curb_run"] == pytest.approx(0.6)
    inbox = api.get(f"{base}/inbox")
    assert any(i["kind"] == "refinery_curbed" for i in inbox["items"])


def test_contracts(api: Client, saves: Path, loaded: LoadedData) -> None:
    _tools().curb(saves, "k", loaded)
    base = BASE.format("k")
    out = api.post(
        f"{base}/refineries/deal",
        json={"side": "sell", "good": "silicon_metal", "months": 12, "volume": 500},
    )
    deal = out["refineries"]["deals"][0]
    assert deal["side"] == "sell" and deal["monthly_volume"] == 500
    api.post(f"{base}/advance")
    plant = api.get(f"{base}/refineries")["plants"][0]
    assert plant["month"]["to_contract"] == pytest.approx(500)
    api.post(
        f"{base}/refineries/deal",
        json={"side": "buy", "good": "silicon_metal", "months": 3, "volume": 1},
        status=400,
    )
