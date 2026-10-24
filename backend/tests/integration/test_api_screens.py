"""M1c additions to the API: values the screens display but must not compute themselves."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.integration.test_api_hiring import BASE, Client, hiring_client


@pytest.fixture
def api(tmp_path: Path) -> Iterator[Client]:
    with hiring_client(tmp_path) as client:
        yield client


def _hire_team(api: Client) -> list[dict[str, Any]]:
    """Job post, advance, generous offers to every candidate, advance. Seed 11 hires several."""
    api.post(
        f"{BASE}/recruitment/searches", {"role": "software_engineer", "channel": "job_post"}, 201
    )
    api.post(f"{BASE}/advance")
    for c in api.get(f"{BASE}/recruitment/candidates"):
        ask = c["candidacy"]["salary_expectation_cents"]
        api.post(
            f"{BASE}/recruitment/candidates/{c['person_id']}/offer",
            {"salary_cents": round(ask * 1.5), "equity_bp": 50},
            201,
        )
    api.post(f"{BASE}/advance")
    staff = [p for p in api.get(f"{BASE}/people") if not p["is_founder"]]
    assert len(staff) >= 2, "seed 11 should hire at least two people at 1.5x"
    return staff


def test_hiring_meta(api: Client) -> None:
    meta = api.get("/api/meta/hiring")
    channels = {c["key"]: c for c in meta["channels"]}
    assert {k: c["energy"] for k, c in channels.items()} == {
        "network": 10,
        "job_post": 4,
        "recruiter": 4,
    }
    assert channels["job_post"]["monthly_cost_cents"] == 50_000
    assert channels["recruiter"]["hire_fee_bp"] == 2_000
    assert [k for k, c in channels.items() if c["repeats"]] == ["job_post"]
    assert (channels["network"]["batch_min"], channels["network"]["batch_max"]) == (2, 4)
    assert meta["interview_energy"] == 6 and meta["reference_check_energy"] == 3
    assert meta["fire_morale_penalty_min"] == 3
    swe = next(r for r in meta["roles"] if r["key"] == "software_engineer")
    assert swe["primary_skills"] == ["software_engineering", "infrastructure"]


def test_new_game_meta_extras(api: Client) -> None:
    scenarios = {s["id"]: s for s in api.get("/api/meta/scenarios")}
    garage = scenarios["garage_bootstrap"]["starting_cash_by_difficulty"]
    assert garage == {
        "easy": 7_500_000,
        "standard": 5_000_000,
        "hard": 3_000_000,
        "ironman": 5_000_000,
    }
    presets = api.get("/api/meta/new-game")["personality_presets"]
    assert all(p["description"] for p in presets)


def test_overview_projection_matches_the_month(api: Client) -> None:
    ov = api.get(f"{BASE}/overview")
    assert ov["stage_label"] == "Solo founder" and ov["runway_low"] is False
    assert ov["team"] == {
        "headcount": 1,
        "on_notice": 0,
        "people_cost_cents": 60_000,
        "payroll_cents": 0,
        "avg_morale": None,
    }
    api.post(f"{BASE}/recruitment/searches", {"role": "designer", "channel": "job_post"}, 201)
    ov = api.get(f"{BASE}/overview")
    projected = {c["account"]: c["amount_cents"] for c in ov["month_costs"]}
    assert projected == {
        "6100_rent": 60_000,
        "6900_general_admin": 50_000,
        "6200_recruiting": 50_000,
    }
    assert ov["month_paid"] == [] and ov["month_total_cents"] == 160_000

    # With no pending offers, the projection is exactly what phase 6 posts.
    after = api.post(f"{BASE}/advance")
    posted = {c["account"]: c["amount_cents"] for c in after["costs_last_month"]}
    assert posted == projected


def test_people_fields_and_fire(api: Client) -> None:
    staff = _hire_team(api)
    hire = staff[0]
    emp = hire["employment"]
    assert emp["tenure_months"] == 1 and emp["start_date_label"] == "Feb 2010"
    assert emp["market_rate_cents"] > 0 and emp["end_date_label"] is None
    salary = emp["salary_cents"]
    monthly = round(salary / 12)
    assert emp["monthly_cost_cents"] == monthly + round(monthly * 0.2) + 60_000

    ov = api.get(f"{BASE}/overview")
    assert ov["stage_label"] == "Garage startup"
    assert ov["team"]["headcount"] == len(staff) + 1
    assert ov["team"]["people_cost_cents"] == sum(
        p["employment"]["monthly_cost_cents"] for p in api.get(f"{BASE}/people")
    )
    morale_before = {p["person_id"]: p["morale"] for p in staff}

    fired = api.post(f"{BASE}/people/{hire['person_id']}/fire")
    ov = api.get(f"{BASE}/overview")
    assert [c["amount_cents"] for c in ov["month_paid"]] == [fired["severance_cents"]]
    assert ov["month_total_cents"] == fired["severance_cents"] + sum(
        c["amount_cents"] for c in ov["month_costs"]
    )
    assert ov["team"]["headcount"] == len(staff)
    # Everyone else loses at least 3 points (6 if the fired person was a culture carrier).
    for p in api.get(f"{BASE}/people"):
        if not p["is_founder"]:
            assert p["morale"] <= max(morale_before[p["person_id"]] - 3, 0) + 1e-9


def test_candidate_knowledge_offer_and_reasons(api: Client) -> None:
    api.post(
        f"{BASE}/recruitment/searches", {"role": "software_engineer", "channel": "job_post"}, 201
    )
    searches = api.get(f"{BASE}/recruitment/searches")
    assert searches[0]["next_batch_date_label"] == "Feb 2010"
    assert searches[0]["opened_date_label"] == "Jan 2010"
    api.post(f"{BASE}/advance")
    cand = api.get(f"{BASE}/recruitment/candidates")[0]
    pid = cand["person_id"]
    assert cand["knowledge"] == {
        "channel": "job_post",
        "interviews": 0,
        "reference_checks": 0,
        "first_interview_date_label": None,
        "profile_known": False,
    }
    assert cand["candidacy"]["expires_date_label"] == "Apr 2010"
    ask = cand["candidacy"]["salary_expectation_cents"]
    preview = api.post(
        f"{BASE}/recruitment/candidates/{pid}/offer-preview", {"salary_cents": ask, "equity_bp": 0}
    )
    assert preview["reasons"][0] == "Pay matches their ask."
    assert any("do not know their interests" in r for r in preview["reasons"])
    assert any("solo founder company is a harder sell" in r for r in preview["reasons"])

    api.post(f"{BASE}/recruitment/candidates/{pid}/interview")
    api.post(f"{BASE}/recruitment/candidates/{pid}/interview")
    profile = api.post(f"{BASE}/recruitment/candidates/{pid}/reference-check")
    assert profile["knowledge"]["interviews"] == 2
    assert profile["knowledge"]["reference_checks"] == 1
    assert profile["knowledge"]["first_interview_date_label"] == "Feb 2010"
    assert profile["knowledge"]["profile_known"] is True
    assert isinstance(profile["work_style_matches_role"], bool)
    preview = api.post(
        f"{BASE}/recruitment/candidates/{pid}/offer-preview",
        {"salary_cents": ask // 2, "equity_bp": 50},
    )
    assert "below 85% of their ask" in preview["reasons"][0]
    assert any("mission" in r for r in preview["reasons"])

    api.post(f"{BASE}/recruitment/candidates/{pid}/offer", {"salary_cents": ask}, 201)
    pending = api.get(f"{BASE}/people/{pid}")["candidacy"]["pending_offer"]
    assert pending["answer_date_label"] == "Mar 2010"


def test_mark_unread(api: Client) -> None:
    api.post(f"{BASE}/recruitment/searches", {"role": "designer", "channel": "network"}, 201)
    api.post(f"{BASE}/advance")
    inbox = api.get(f"{BASE}/inbox")
    item = inbox["items"][0]
    api.post(f"{BASE}/inbox/{item['item_id']}/read")
    again = api.post(f"{BASE}/inbox/{item['item_id']}/unread")
    assert again["read"] is False
    assert api.get(f"{BASE}/inbox")["unread"] == inbox["unread"]
    api.post(f"{BASE}/inbox/999/unread", status=404)
