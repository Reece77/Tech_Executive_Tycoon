"""M1b API: people, recruitment, offers, inbox, energy, overview, and meta endpoints."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api import find_forbidden_keys
from tst.api.app import create_app
from tst.config import Settings, get_settings

BASE = "/api/saves/m1b"


class Client:
    """TestClient wrapper that checks every JSON response for hidden fields (ADR-0007)."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    def call(self, method: str, url: str, status: int = 200, **kwargs: Any) -> Any:
        res = self.client.request(method, url, **kwargs)
        assert res.status_code == status, (url, res.status_code, res.text)
        body = res.json()
        assert find_forbidden_keys(body) == [], url
        return body

    def get(self, url: str, status: int = 200) -> Any:
        return self.call("GET", url, status)

    def post(self, url: str, json: Any = None, status: int = 200) -> Any:
        return self.call("POST", url, status, json=json)


@pytest.fixture
def api(tmp_path: Path) -> Iterator[Client]:
    with hiring_client(tmp_path) as client:
        yield client


@contextmanager
def hiring_client(tmp_path: Path) -> Iterator[Client]:
    """A fresh save "m1b" (seed 11, ex-big-tech founders, mission AI and Enterprise)."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=tmp_path / "saves")
    with TestClient(app) as c:
        client = Client(c)
        client.post(
            "/api/saves",
            {
                "name": "m1b",
                "seed": 11,
                "scenario": "ex_big_tech_founders",
                "company_name": "Test Co",
                "mission": ["ai", "enterprise"],
            },
            status=201,
        )
        yield client


def test_full_hiring_flow(api: Client) -> None:
    ov = api.get(f"{BASE}/overview")
    assert ov["mission"] == ["ai", "enterprise"]
    assert ov["energy"] == {"energy": 60, "max": 60, "adjustments": []}
    assert ov["headcount"] == 1 and ov["stage"] == 0

    people = api.get(f"{BASE}/people")
    assert len(people) == 1
    founder = api.get(f"{BASE}/people/{people[0]['person_id']}")
    assert founder["is_founder"] and founder["level"] == "exec"
    assert all(s["range"]["min"] == s["range"]["max"] for s in founder["skills"])
    assert founder["interests"] is not None and founder["potential_phrase"]

    search = api.post(
        f"{BASE}/recruitment/searches", {"role": "software_engineer", "channel": "job_post"}, 201
    )
    assert search["monthly_cost_cents"] == 50_000 and search["status"] == "open"
    assert api.get(f"{BASE}/founder/energy") == {"energy": 55, "max": 60, "adjustments": []}
    assert [s["search_id"] for s in api.get(f"{BASE}/recruitment/searches")] == [1]

    api.post(f"{BASE}/advance")
    candidates = api.get(f"{BASE}/recruitment/candidates")
    assert 6 <= len(candidates) <= 10
    first = candidates[0]
    assert first["candidacy"]["channel"] == "job_post"
    assert first["employment"] is None and first["morale"] is None
    pid = first["person_id"]
    before = api.get(f"{BASE}/people/{pid}")
    assert before["interests"] is None and before["work_style"] is None

    after = api.post(f"{BASE}/recruitment/candidates/{pid}/interview")
    assert after["interests"] is not None and after["work_style"] is not None
    widths = {s["key"]: s["range"]["max"] - s["range"]["min"] for s in after["skills"]}
    old = {s["key"]: s["range"]["max"] - s["range"]["min"] for s in before["skills"]}
    assert all(widths[k] <= old[k] for k in widths)
    api.post(f"{BASE}/recruitment/candidates/{pid}/reference-check")
    assert api.get(f"{BASE}/founder/energy")["energy"] == 60 - 8 - 4  # energy reset at turn end

    ask = first["candidacy"]["salary_expectation_cents"]
    preview = api.post(
        f"{BASE}/recruitment/candidates/{pid}/offer-preview",
        {"salary_cents": ask, "equity_bp": 50},
    )
    assert preview["hint"] in ("likely", "uncertain", "unlikely")
    assert preview["expectation_cents"] == ask
    assert preview["floor_cents"] == -(-ask * 85 // 100)
    assert preview["problems"] == [] and preview["option_pool_left_bp"] == 1000
    low = api.post(
        f"{BASE}/recruitment/candidates/{pid}/offer-preview",
        {"salary_cents": ask // 2, "equity_bp": 300},
    )
    assert low["hint"] == "unlikely" and len(low["problems"]) == 1

    offer = api.post(
        f"{BASE}/recruitment/candidates/{pid}/offer",
        {"salary_cents": round(ask * 1.5), "equity_bp": 50},
        201,
    )
    assert offer["status"] == "pending"
    withdrawn = api.post(f"{BASE}/recruitment/offers/{offer['offer_id']}/withdraw")
    assert withdrawn["status"] == "withdrawn"
    offer = api.post(
        f"{BASE}/recruitment/candidates/{pid}/offer",
        {"salary_cents": round(ask * 1.5), "equity_bp": 50},
        201,
    )

    ov = api.post(f"{BASE}/advance")
    staff = api.get(f"{BASE}/people")
    hired = [p for p in staff if p["person_id"] == pid]
    assert hired, "a 1.5x offer should be accepted"
    assert hired[0]["employment"]["salary_cents"] == round(ask * 1.5)
    assert hired[0]["morale"] is not None
    assert ov["headcount"] == 2 and ov["stage"] == 1
    assert ov["payroll_cents"] > 0 and ov["avg_morale"] is not None
    labels = {c["account"] for c in ov["costs_last_month"]}
    assert {"6000_salaries", "6010_benefits", "6100_rent", "6900_general_admin"} <= labels
    assert ov["latest_inbox"] and ov["unread_inbox"] >= 2

    inbox = api.get(f"{BASE}/inbox")
    kinds = [i["kind"] for i in inbox["items"]]
    assert "offer_accepted" in kinds and "candidates_arrived" in kinds
    item = inbox["items"][0]
    read = api.post(f"{BASE}/inbox/{item['item_id']}/read")
    assert read["read"] is True
    assert api.get(f"{BASE}/inbox?unread_only=true")["unread"] == inbox["unread"] - 1

    profile = api.get(f"{BASE}/people/{pid}")
    assert len(profile["morale_history"]) == 1
    fired = api.post(f"{BASE}/people/{pid}/fire")
    assert fired["severance_cents"] == profile["employment"]["severance_cents"] > 0
    assert all(p["person_id"] != pid for p in api.get(f"{BASE}/people"))
    api.post(f"{BASE}/recruitment/searches/1/close")
    # A closed search stays listed while its candidates are still available (M1c).
    searches = api.get(f"{BASE}/recruitment/searches")
    assert [(s["search_id"], s["status"]) for s in searches] == [(1, "closed")]
    assert searches[0]["open_candidates"] > 0
    assert searches[0]["next_batch_date_label"] is None


@pytest.mark.parametrize(
    ("method", "url", "body", "status", "code"),
    [
        ("GET", f"{BASE}/people/999", None, 404, "unknown_person"),
        ("POST", f"{BASE}/people/1/fire", None, 400, "invalid_action"),
        ("POST", f"{BASE}/recruitment/candidates/999/interview", None, 404, "unknown_candidate"),
        ("POST", f"{BASE}/recruitment/searches/9/close", None, 404, "unknown_search"),
        ("POST", f"{BASE}/recruitment/offers/9/withdraw", None, 404, "unknown_offer"),
        ("POST", f"{BASE}/inbox/9/read", None, 404, "unknown_inbox_item"),
        (
            "POST",
            f"{BASE}/recruitment/searches",
            {"role": "astronaut", "channel": "network"},
            400,
            "unknown_role",
        ),
    ],
)
def test_errors(api: Client, method: str, url: str, body: Any, status: int, code: str) -> None:
    assert api.call(method, url, status, json=body)["code"] == code


def test_energy_runs_out(api: Client) -> None:
    for _ in range(6):  # 60 energy, 10 each (M4c)
        api.post(f"{BASE}/recruitment/searches", {"role": "designer", "channel": "network"}, 201)
    res = api.post(f"{BASE}/recruitment/searches", {"role": "designer", "channel": "network"}, 400)
    assert res["code"] == "insufficient_energy"


def test_new_game_meta(api: Client) -> None:
    meta = api.get("/api/meta/new-game")
    assert [s["id"] for s in meta["scenarios"]] == [
        "garage_bootstrap",
        "ex_big_tech_founders",
        "funded_spinout",
    ]
    assert meta["difficulties"] == ["easy", "standard", "hard", "ironman"]
    assert {b["key"] for b in meta["backgrounds"] if b["selectable"]} == {
        "engineer",
        "salesperson",
        "academic",
        "ex_big_tech",
    }
    assert len(meta["skills"]) == 25 and len(meta["interests"]) == 13
    assert meta["founder_rules"] == {
        "skill_base": 5.0,
        "skill_points": 70,
        "skill_cap": 18.0,
        "age_min": 22,
        "age_max": 60,
        "default_age": 28,
        "default_region": "north_america",
        "mission_size": 2,
    }


def test_founder_preview(api: Client) -> None:
    ok = api.post("/api/meta/founder-preview", {"background": "engineer"})
    assert ok["errors"] == [] and ok["points_remaining"] == 0 and ok["points_spent"] == 70
    values = {s["key"]: s["value"] for s in ok["skills"]}
    assert values["software_engineering"] == 16
    bad = api.post(
        "/api/meta/founder-preview",
        {"background": "engineer", "allocation": {"software_engineering": 20}, "age": 70},
    )
    assert bad["points_remaining"] == 50
    assert bad["errors"] == [
        "allocation spends 20 points; spend all 70",
        "skills above the cap of 18: software_engineering = 28",
        "age must be 22-60, got 70",
    ]


def test_create_with_bad_mission(api: Client) -> None:
    res = api.post(
        "/api/saves",
        {"name": "x", "scenario": "garage_bootstrap", "company_name": "X", "mission": ["ai"]},
        400,
    )
    assert res["code"] == "invalid_mission"
