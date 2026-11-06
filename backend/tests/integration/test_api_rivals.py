"""M5 API: rivals, profile, market news, approaches with a counter band, poach searches.
Every response passes the hidden-field check (ADR-0007) in Client.call."""

from __future__ import annotations

from pathlib import Path

from tests.integration.test_api_hiring import BASE, hiring_client
from tst.config import Settings
from tst.db import repository
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.rivals.decisions import approach


def test_rivals_profile_news_and_poach(tmp_path: Path, loaded: LoadedData) -> None:
    with hiring_client(tmp_path) as api:
        rivals = api.get(f"{BASE}/rivals")
        assert rivals["established"] == 39 and rivals["startups_alive"] == 0  # M12a +4, M12b +12
        names = {r["name"]: r for r in rivals["rivals"]}
        salesforce = names["Salesforce"]
        assert salesforce["personality_label"] == "Premium"
        assert salesforce["money_label"] in ("deep pockets", "comfortable", "tight")
        assert salesforce["stance"] == "not competing"  # the player sells nothing yet
        assert api.get(f"{BASE}/rivals?view=markets")["rivals"] == []
        api.post(f"{BASE}/advance")
        profile = api.get(f"{BASE}/rivals/{salesforce['company_id']}")
        assert profile["name"] == "Salesforce" and len(profile["key_people"]) == 8
        person = profile["key_people"][0]
        assert len(person["top_skills"]) == 3 and person["potential_phrase"]
        assert all(s["range"]["min"] < s["range"]["max"] for s in person["top_skills"])  # strangers
        assert profile["segments"] and profile["poach_energy"] == 10
        news = api.get(f"{BASE}/news")
        assert news["months"] and all(m["moves"] for m in news["months"])
        assert {move["tag"] for m in news["months"] for move in m["moves"]} <= {
            "Price",
            "Push",
            "Enter",
            "Cut",
            "Approach",
            "Launch",
            "Funding",
            "Founded",
            "Failed",
        }
        api.get(f"{BASE}/rivals/1", status=404)

        search = api.post(
            f"{BASE}/recruitment/searches",
            {"role": "software_engineer", "channel": "poach", "rival_id": salesforce["company_id"]},
            201,
        )
        assert search["rival_name"] == "Salesforce" and search["channel"] == "poach"
        channels = {c["key"]: c for c in api.get("/api/meta/hiring")["channels"]}
        assert channels["poach"]["energy"] == 10 and not channels["poach"]["repeats"]
        api.post(f"{BASE}/advance")
        poached = [
            c
            for c in api.get(f"{BASE}/recruitment/candidates")
            if c["candidacy"]["search_id"] == search["search_id"]
        ]
        assert 1 <= len(poached) <= 4
        api.post(
            f"{BASE}/recruitment/searches",
            {"role": "designer", "channel": "network", "rival_id": salesforce["company_id"]},
            400,
        )


def test_an_approach_shows_a_band_and_a_counter_preview(tmp_path: Path, loaded: LoadedData) -> None:
    with hiring_client(tmp_path) as api:
        api.post(
            f"{BASE}/recruitment/searches",
            {"role": "software_engineer", "channel": "job_post"},
            201,
        )
        api.post(f"{BASE}/advance")
        for c in api.get(f"{BASE}/recruitment/candidates")[:5]:
            api.post(f"{BASE}/recruitment/candidates/{c['person_id']}/interview")
            api.post(
                f"{BASE}/recruitment/candidates/{c['person_id']}/offer",
                {"salary_cents": c["candidacy"]["salary_expectation_cents"] * 2, "equity_bp": 0},
                201,
            )
        api.post(f"{BASE}/advance")
        staff = [p for p in api.get(f"{BASE}/people") if not p["is_founder"]]
        assert staff
        path = repository.existing_save_path(
            Settings(save_dir=tmp_path / "saves").resolved_save_dir(), "m1b"
        )
        with repository.open_session(path) as session, session.begin():
            state = load_state(session)
            rival = next(c for c in state.companies if c.name == "Zoho")
            sync_state(
                session,
                state,
                approach(state, rival, staff[0]["person_id"], loaded.balance, loaded.game_data),
            )
        (open_one,) = api.get(f"{BASE}/approaches")
        assert open_one["rival_name"] == "Zoho" and open_one["offer_cents"] > 0
        assert open_one["band"] in ("likely to stay", "might go", "likely to go")
        preview = api.post(
            f"{BASE}/approaches/{open_one['approach_id']}/counter-preview",
            {"salary_cents": open_one["offer_cents"] * 2},
        )
        assert preview["band_now"] == open_one["band"]
        assert preview["band_after"] == "likely to stay"
        api.post(f"{BASE}/approaches/999/counter-preview", {"salary_cents": 1}, status=404)


def test_each_rival_product_shows_its_market(tmp_path: Path, loaded: LoadedData) -> None:
    """Reece's playtest 3: the Rival screen named products but not their market."""
    with hiring_client(tmp_path) as api:
        names = {r["name"]: r for r in api.get(f"{BASE}/rivals")["rivals"]}
        profile = api.get(f"{BASE}/rivals/{names['Salesforce']['company_id']}")
        (crm,) = (p for p in profile["products"] if p["name"] == "Sales Cloud")
        assert crm["category_label"] == loaded.game_data.category("b2b_saas").label
        segments = {
            s["segment_label"] for s in profile["segments"] if s["product_name"] == crm["name"]
        }
        assert segments <= set(crm["segment_labels"]) and crm["segment_labels"]
        assert crm["region_labels"] and crm["region_labels"][0] == "North America"
