"""M9 API and CLI: cities and offices, a unit's office, the lease preview, a product's
regions and launch, regional prices, the market's region picker, search cities and people's
cities (formulas.md 19.7)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from tests.helpers import (
    FIRST_PRODUCT,
    make_person,
    move_save_directors,
    with_employee,
    with_product,
)
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.cli import app as cli_app
from tst.config import Settings, get_settings
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.actions import CreateUnit, MovePerson, apply_action
from tst.sim.rng import RngFactory

SAVE = "geo"
BASE = f"/api/saves/{SAVE}"
PRODUCT = FIRST_PRODUCT


def _build(save_dir: Path, loaded: LoadedData) -> Path:
    path = create_save(
        SAVE, 5, "funded_spinout", company_name="Geo Co", data=loaded, save_dir=save_dir
    )
    move_save_directors(path)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        state = before
        for pid in (2, 3, 4):
            state = with_employee(loaded, state, make_person(loaded, pid), 9_000_000)
        state = with_product(state, quality=60, feature_points=200, brand=40)
        for action in (CreateUnit(1, "team", "Platform"), *(MovePerson(1, p, 1) for p in (2, 3))):
            state = apply_action(
                state, action, RngFactory(1), loaded.balance, loaded.game_data, {}, seq=1
            ).new_state
        state = replace(state, next_ids=replace(state.next_ids, person=5))
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


def test_offices_lease_move_and_close(api: tuple[Client, Path]) -> None:
    client, _ = api
    geo = client.get(f"{BASE}/geo")
    assert geo["hq_city"] == "san_francisco" and geo["home_region"] == "north_america"
    assert [o["office_id"] for o in geo["offices"]] == [None]
    berlin = next(c for c in geo["cities"] if c["key"] == "berlin")
    assert (berlin["salary_index"], berlin["rent_index"]) == (0.65, 0.45)
    assert berlin["example_rate_cents"] == 6_548_100  # $115,000 x 0.65 x 0.876
    preview = client.get(f"{BASE}/geo/lease-preview?city=berlin&seats=50")
    assert (preview["monthly_rent_cents"], preview["fit_out_cents"]) == (1_012_500, 3_037_500)
    out = client.post(f"{BASE}/geo/offices", {"city": "berlin", "seats": 25})
    office = out["geo"]["offices"][1]
    assert (office["city"], office["seats"], office["people"]) == ("berlin", 25, 0)
    assert out["energy"]["energy"] == 46  # 60 - 4 in the fixture's org moves - 10
    moved = client.post(f"{BASE}/geo/units/1/office", {"office_id": office["office_id"]})
    office = moved["geo"]["offices"][1]
    assert office["people"] == 2 and [u["name"] for u in office["units"]] == ["Platform"]
    person = client.get(f"{BASE}/people/2")
    assert person["city"] == "berlin" and person["city_label"] == "Berlin"
    closed = client.post(f"{BASE}/geo/offices/{office['office_id']}/close")
    assert [o["office_id"] for o in closed["geo"]["offices"]] == [None]
    client.post(f"{BASE}/geo/offices", {"city": "atlantis", "seats": 25}, status=400)


def test_product_regions_launch_and_price(api: tuple[Client, Path]) -> None:
    client, _ = api
    regions = client.get(f"{BASE}/products/{PRODUCT}/regions")
    rows = {r["region"]: r for r in regions["regions"]}
    assert rows["north_america"]["status"] == "home"
    europe = rows["europe"]
    assert europe["status"] == "not_launched" and europe["launch_cost_cents"] == 4_000_000
    assert europe["rivals"] > 0 and europe["addressable"] > 0
    assert europe["local_presence"] is False and "x 0.6" in europe["reach_note"]
    out = client.post(f"{BASE}/products/{PRODUCT}/regions", {"region": "europe"})
    europe = next(r for r in out["regions"]["regions"] if r["region"] == "europe")
    assert europe["status"] == "localizing" and europe["status_label"].startswith("Localizing")
    assert europe["segments"][0]["price_cents"] == 4_500
    priced = client.post(
        f"{BASE}/products/{PRODUCT}/regions/europe/price",
        {"segment": "smb", "price_cents": 3_900},
    )
    europe = next(r for r in priced["regions"]["regions"] if r["region"] == "europe")
    assert europe["segments"][0]["price_cents"] == 3_900
    client.post(f"{BASE}/products/{PRODUCT}/regions", {"region": "europe"}, status=400)


def test_market_region_picker(api: tuple[Client, Path]) -> None:
    client, _ = api
    home = client.get(f"{BASE}/markets/b2b_saas")
    assert home["region"] == "north_america" and len(home["regions"]) == 7
    europe = client.get(f"{BASE}/markets/b2b_saas?region=europe")
    smb = next(s for s in europe["segments"] if s["segment"] == "smb")
    assert europe["region_label"] == "Europe" and smb["reference_price_cents"] == 4_500
    names = {p["company_name"] for s in europe["segments"] for p in s["products"]}
    assert "SAP" in names and "Salesforce" in names
    assert "SAP" not in {p["company_name"] for s in home["segments"] for p in s["products"]}


def test_search_city_and_candidates(api: tuple[Client, Path]) -> None:
    client, _ = api
    search = client.post(
        f"{BASE}/recruitment/searches",
        {"role": "software_engineer", "channel": "job_post", "city": "bangalore"},
        status=201,
    )
    assert search["city"] == "bangalore" and search["city_label"] == "Bangalore"
    client.post(f"{BASE}/advance")
    candidates = client.get(f"{BASE}/recruitment/candidates")
    cities = {c["city"] for c in candidates}
    assert "bangalore" in cities
    movers = [c for c in candidates if c["city"] != "bangalore"]
    assert all(c["would_relocate"] for c in movers)
    client.post(
        f"{BASE}/recruitment/searches",
        {"role": "designer", "channel": "network", "city": "anywhere"},
        status=400,
    )


def test_cli_cities_offices_lease_and_launch(api: tuple[Client, Path], tmp_path: Path) -> None:
    _, path = api
    runner = CliRunner(env={"TST_SAVE_DIR": str(path.parent)})

    def run(*args: str) -> str:
        result = runner.invoke(cli_app, list(args))
        assert result.exit_code == 0, result.output
        return result.output

    assert "Bangalore" in run("cities", "--save", SAVE)
    assert "$10,125.00 a month" in run("lease", "--save", SAVE, "--city", "berlin", "--seats", "50")
    assert "Berlin" in run("offices", "--save", SAVE)
    out = run("launch-region", "--save", SAVE, "--product", str(PRODUCT), "--region", "europe")
    assert "Localizing for Europe; live in Apr 2010" in out
    assert "Localizing until Apr 2010" in run("regions", "--save", SAVE, "--product", str(PRODUCT))
