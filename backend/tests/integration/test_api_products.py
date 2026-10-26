"""M3a API: categories, markets, the player's products and their actions, the price
preview, MRR and ARR, and founder scouting. Every response is checked for hidden fields and
the formulas.md 11.13 forbidden names."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import make_person, with_employee
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.repository import create_save, load_state, open_session, run_turn
from tst.db.state_io import sync_state
from tst.loader import LoadedData
from tst.sim.state import with_person

SAVE = "m3a"
BASE = f"/api/saves/{SAVE}"
PRODUCT = 13


def staff(path: Path, loaded: LoadedData, roles: tuple[str, ...]) -> None:
    """Employees 2.. in the given roles, skills at 11, in the company root."""
    with open_session(path) as session, session.begin():
        before = load_state(session)
        state = before
        for pid, role in enumerate(roles, start=2):
            person = make_person(loaded, pid, role)
            skills = person.skills.updated(dict.fromkeys(person.skills.keys(), 11.0))
            person = replace(person, skills=skills, tags=())
            state = with_employee(loaded, state, person, 9_000_000)
            state = with_person(state, person)
        state = replace(state, next_ids=replace(state.next_ids, person=2 + len(roles)))
        sync_state(session, before, state)


@pytest.fixture
def setup(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[Client, Path]]:
    save_dir = tmp_path / "saves"
    path = create_save(
        SAVE, 8, "funded_spinout", company_name="Prod Co", data=loaded, save_dir=save_dir
    )
    staff(path, loaded, ("software_engineer",) * 3 + ("account_executive", "marketer"))
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client), path


def create(api: Client) -> dict[str, Any]:
    body = {"name": "Pipeline", "category": "b2b_saas", "segments": ["smb", "mid_market"]}
    out: dict[str, Any] = api.post(f"{BASE}/products", body, status=201)
    return out


def test_categories_and_markets(setup: tuple[Client, Path]) -> None:
    api, _ = setup
    categories = api.get(f"{BASE}/categories")
    assert [c["key"] for c in categories] == [
        "b2b_saas",
        "dev_tools",
        "consumer_apps",
        "cybersecurity",
    ]
    smb = categories[0]["segments"][0]
    assert (smb["segment"], smb["addressable"], smb["reach"]) == ("smb", 400_000, "self_serve")
    market = api.get(f"{BASE}/markets/b2b_saas")
    by_segment = {s["segment"]: s for s in market["segments"]}
    smb_products = by_segment["smb"]["products"]
    assert {p["company_name"] for p in smb_products} == {"Salesforce", "Zoho"}
    assert sum(p["share_of_served"] for p in smb_products) == pytest.approx(1)
    assert all(not p["is_player"] and p["mrr_cents"] > 0 for p in smb_products)
    assert {p["name"] for p in by_segment["enterprise"]["products"]} == {
        "Sales Cloud",
        "CRM On Demand",
    }
    api.get(f"{BASE}/markets/hardware", status=400)


def test_create_staff_launch_and_sunset_through_the_api(
    setup: tuple[Client, Path], loaded: LoadedData
) -> None:
    api, path = setup
    out = create(api)
    product = out["product"]
    assert (product["product_id"], product["status"], product["lifecycle_label"]) == (
        PRODUCT,
        "in_development",
        "In development",
    )
    assert out["energy"]["energy"] == 96
    assert product["launch"]["ready"] is False
    assert any("quality" in m for m in product["launch"]["missing"])
    refused = api.post(f"{BASE}/products/{PRODUCT}/launch", status=400)
    assert refused["code"] == "launch_not_ready" and "a price for SMB" in refused["message"]

    api.post(f"{BASE}/products/{PRODUCT}/price", {"segment": "smb", "price_cents": 4000})
    api.post(f"{BASE}/products/{PRODUCT}/price", {"segment": "mid_market", "price_cents": 70_000})
    api.post(f"{BASE}/products/{PRODUCT}/price", {"segment": "smb", "price_cents": 0}, status=400)
    out = api.post(f"{BASE}/products/{PRODUCT}/assign", {"unit_id": None})
    product = out["product"]
    assert product["assigned_units"] == [{"unit_id": None, "name": "Prod Co"}]
    assert [b["person_id"] for b in product["builders"]] == [1, 2, 3, 4]
    assert [s["person_id"] for s in product["sellers"]] == [5]
    assert [m["person_id"] for m in product["marketers"]] == [6]
    assert product["pace"] in {"fast", "steady", "slow"}
    out = api.post(f"{BASE}/products/{PRODUCT}/marketing", {"budget_cents": 1_000_000})
    assert out["product"]["marketing_budget_cents"] == 1_000_000

    for _ in range(12):
        if api.get(f"{BASE}/products/{PRODUCT}")["launch"]["ready"]:
            break
        run_turn(path, loaded)
    product = api.get(f"{BASE}/products/{PRODUCT}")
    assert product["launch"] == {"ready": True, "missing": []}
    out = api.post(f"{BASE}/products/{PRODUCT}/launch")
    assert out["product"]["status"] == "live" and out["unread_inbox"] >= 1
    for _ in range(3):
        run_turn(path, loaded)
    product = api.get(f"{BASE}/products/{PRODUCT}")
    assert product["mrr_cents"] > 0 and product["history"]
    assert product["lifecycle_label"] in {"Growth", "Mature", "Live"}
    smb = next(s for s in product["segments"] if s["segment"] == "smb")
    assert smb["customers"] > 0 and smb["appeal"] is not None and smb["churn_rate"] > 0
    market = api.get(f"{BASE}/markets/b2b_saas")
    smb_market = next(s for s in market["segments"] if s["segment"] == "smb")
    assert any(p["is_player"] for p in smb_market["products"])
    overview = api.get(f"{BASE}/overview")
    assert overview["mrr_cents"] > 0 and overview["arr_cents"] == 12 * overview["mrr_cents"]
    assert overview["history"][-1]["mrr_cents"] == overview["mrr_cents"]
    assert [p["product_id"] for p in api.get(f"{BASE}/products")] == [PRODUCT]
    screens_get_what_they_show(api, product, overview)

    out = api.post(f"{BASE}/products/{PRODUCT}/sunset")
    assert out["product"]["status"] == "sunset" and out["product"]["lifecycle_label"] == "Sunset"
    api.post(f"{BASE}/products/{PRODUCT}/sunset", status=400)


def screens_get_what_they_show(
    api: Client, product: dict[str, Any], overview: dict[str, Any]
) -> None:
    """The M3b screens' values come from the API (CLAUDE.md 7): totals, trends, last month's
    flows, price scores, hosting, the portfolio tiles, the unit's product, inbox kinds."""
    segments = product["segments"]
    assert product["customers"] == pytest.approx(sum(s["customers"] for s in segments))
    assert product["new_last_month"] == pytest.approx(sum(s["new_last_month"] for s in segments))
    last = max(m["turn"] for m in product["history"])
    smb_last = next(m for m in product["history"] if m["turn"] == last and m["segment"] == "smb")
    smb = next(s for s in segments if s["segment"] == "smb")
    assert smb["new_last_month"] == pytest.approx(smb_last["new"])
    assert smb["churned_last_month"] == pytest.approx(smb_last["churned"])
    assert smb["price_score"] == pytest.approx(62.5) and smb["counts_users"] is False
    assert product["launched_label"] is not None and product["hosting_cents"] > 0
    assert product["brand_trend"] == "rising"  # $10,000 a month from brand 0
    assert product["customer_trend"] is not None and product["mrr_change"] is not None

    portfolio = api.get(f"{BASE}/portfolio")
    assert portfolio["mrr_cents"] == overview["mrr_cents"]
    assert portfolio["arr_cents"] == overview["arr_cents"]
    assert portfolio["paying_customers"] == pytest.approx(product["customers"])
    assert portfolio["consumer_users"] == 0
    assert portfolio["hosting_cents"] == product["hosting_cents"]
    assert portfolio["marketing_cents"] == 1_000_000
    assert portfolio["previous_label"] is not None and portfolio["stage_label"]
    assert overview["month_revenue_cents"] == product["mrr_cents"]

    market = api.get(f"{BASE}/markets/b2b_saas")
    assert market["annual_growth"] == pytest.approx(0.20)
    by_key = {s["segment"]: s for s in market["segments"]}
    assert by_key["smb"]["player_sells"] and not by_key["enterprise"]["player_sells"]
    smb_market = by_key["smb"]
    assert smb_market["unserved"] == pytest.approx(smb_market["addressable"] - smb_market["served"])
    assert smb_market["reference_price_cents"] == 5000
    assert smb_market["weights"] == {
        "quality": 0.25,
        "price": 0.35,
        "brand": 0.15,
        "features": 0.25,
    }
    zoho = next(p for p in smb_market["products"] if p["name"] == "Zoho CRM")
    assert zoho["price_score"] == 100

    root = api.get(f"{BASE}/org")["units"][0]
    assert (root["unit_id"], root["product_id"], root["product_name"]) == (
        None,
        PRODUCT,
        "Pipeline",
    )
    launched = api.get(f"{BASE}/inbox?kind=product_launched&kind=first_customer")
    assert launched["total"] >= 1
    assert {i["kind"] for i in launched["items"]} <= {"product_launched", "first_customer"}
    assert api.get(f"{BASE}/inbox?kind=offer_accepted")["total"] == 0


def test_cancel_a_product_in_development(setup: tuple[Client, Path]) -> None:
    api, _ = setup
    create(api)
    api.post(f"{BASE}/products/{PRODUCT}/assign", {"unit_id": None})
    refused = api.post(f"{BASE}/products/{PRODUCT}/sunset", status=400)
    assert "cancel its development instead" in refused["message"]
    out = api.post(f"{BASE}/products/{PRODUCT}/cancel")
    assert set(out) == {"energy", "unread_inbox"}
    assert out["energy"]["energy"] == 100 - 4 - 2 - 3
    assert api.get(f"{BASE}/products") == []
    api.get(f"{BASE}/products/{PRODUCT}", status=404)
    api.post(f"{BASE}/products/{PRODUCT}/cancel", status=404)
    again = create(api)["product"]["product_id"]  # the root is free for the next product
    api.post(f"{BASE}/products/{again}/assign", {"unit_id": None})


def test_segments_unassign_and_errors(setup: tuple[Client, Path]) -> None:
    api, _ = setup
    create(api)
    out = api.post(f"{BASE}/products/{PRODUCT}/segments", {"segment": "enterprise"})
    assert [s["segment"] for s in out["product"]["segments"]] == [
        "enterprise",
        "mid_market",
        "smb",
    ]
    api.post(f"{BASE}/products/{PRODUCT}/segments", {"segment": "consumer"}, status=400)
    api.post(f"{BASE}/products/{PRODUCT}/unassign", {"unit_id": None}, status=400)
    api.post(f"{BASE}/products/{PRODUCT}/assign", {"unit_id": None})
    out = api.post(f"{BASE}/products/{PRODUCT}/unassign", {"unit_id": None})
    assert out["product"]["assigned_units"] == []
    api.get(f"{BASE}/products/1", status=404)  # Salesforce's product is not the player's
    api.post(f"{BASE}/products/999/launch", status=404)
    bad = {"name": "X", "category": "b2b_saas", "segments": ["consumer"]}
    assert api.post(f"{BASE}/products", bad, status=400)["code"] == "product_rule"


def test_price_preview_compares_against_current_competitors(setup: tuple[Client, Path]) -> None:
    api, _ = setup
    create(api)
    api.post(f"{BASE}/products/{PRODUCT}/price", {"segment": "smb", "price_cents": 4000})
    url = f"{BASE}/products/{PRODUCT}/price-preview"
    at_40 = api.post(url, {"segment": "smb", "price_cents": 4000})
    at_25 = api.post(url, {"segment": "smb", "price_cents": 2500})
    assert at_40["price_score"] == pytest.approx(62.5)
    assert at_25["price_score"] == 100
    assert at_25["choice_share"] > at_40["choice_share"]
    assert at_40["current_appeal"] == pytest.approx(at_40["appeal"])
    assert at_25["current_price_cents"] == 4000
    assert at_25["current_price_score"] == pytest.approx(62.5)
    assert at_25["revenue_per_customer_change"] == pytest.approx(-0.375)
    unpriced = api.post(url, {"segment": "mid_market", "price_cents": 70_000})
    assert unpriced["current_price_cents"] is None
    assert unpriced["revenue_per_customer_change"] is None
    assert "customers" not in at_25 and "new" not in at_25
    api.post(url, {"segment": "enterprise", "price_cents": 100}, status=400)


def test_founder_scouts_a_search(setup: tuple[Client, Path], loaded: LoadedData) -> None:
    api, path = setup
    search = api.post(
        f"{BASE}/recruitment/searches", {"role": "designer", "channel": "network"}, status=201
    )
    run_turn(path, loaded)
    before = api.get(f"{BASE}/founder/energy")["energy"]
    out = api.post(f"{BASE}/recruitment/searches/{search['search_id']}/scout")
    assert out["energy"]["energy"] == before - 20
    api.post(f"{BASE}/recruitment/searches/999/scout", status=404)


def test_products_meta(setup: tuple[Client, Path]) -> None:
    api, _ = setup
    meta = api.get("/api/meta/products")
    assert meta["energy_costs"] == {
        "create_product": 4,
        "set_price": 1,
        "add_segment": 2,
        "assign_unit": 2,
        "unassign_unit": 2,
        "set_marketing": 1,
        "launch_product": 3,
        "sunset_product": 3,
        "cancel_product": 3,
        "scout_search": 20,
    }
    assert (meta["start_quality"], meta["launch_min_quality"], meta["launch_min_feature"]) == (
        10,
        25,
        30,
    )
