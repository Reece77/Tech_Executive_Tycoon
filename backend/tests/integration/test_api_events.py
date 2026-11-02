"""M6 API: events with choices as words, choosing, a critical event blocking Continue, the
follow-up next month, storylines, relationship labels, team mood, headlines, and the AI
writing settings (never the key). Every response passes the hidden-field check."""

from __future__ import annotations

from pathlib import Path

from tests.helpers import open_event
from tests.integration.test_api_hiring import BASE, hiring_client
from tst.db import repository
from tst.loader import LoadedData


def test_events_choose_block_and_follow_up(tmp_path: Path, loaded: LoadedData) -> None:
    with hiring_client(tmp_path) as api:
        path = repository.save_path(tmp_path / "saves", "m1b")
        event_id = open_event(path, loaded, "quiet_tax_credit", severity="minor")
        events = api.get(f"{BASE}/events")
        assert events["to_answer"] >= 1 and events["blocking_event_id"] is None
        card = next(e for e in events["open"] if e["event_id"] == event_id)
        assert card["written_by"] == "template" and len(card["choices"]) == 2
        assert any("brings in about $" in w for w in card["choices"][0]["effects"])
        before = api.get(f"{BASE}/overview")["cash_cents"]
        out = api.post(f"{BASE}/events/{event_id}/choose", {"choice": "A"})
        assert out["event"]["status"] == "answered" and out["event"]["chosen"] == "A"
        assert api.get(f"{BASE}/overview")["cash_cents"] > before
        assert api.post(f"{BASE}/events/{event_id}/choose", {"choice": "B"}, 409)["code"] == (
            "invalid_event_choice"
        )
        api.get(f"{BASE}/events/99999", 404)

        crit = open_event(path, loaded, "runway_payroll_crunch", severity="critical")
        assert api.get(f"{BASE}/events")["blocking_event_id"] == crit
        blocked = api.post(f"{BASE}/advance", status=409)
        assert blocked["code"] == "critical_event_open" and blocked["event_id"] == crit
        api.post(f"{BASE}/events/{crit}/choose", {"choice": "B"})
        api.post(f"{BASE}/advance")
        titles = [e["title"] for e in api.get(f"{BASE}/events")["open"]]
        assert any("morning after" in t for t in titles)
        inbox = [
            *api.get(f"{BASE}/inbox")["items"],
            *api.get(f"{BASE}/inbox?archived=true")["items"],
        ]
        assert {"event", "critical_event"} <= {i["kind"] for i in inbox}
        assert api.get(f"{BASE}/news")["headlines"]  # written after the turn
        assert isinstance(api.get(f"{BASE}/storylines"), list)
        assert api.get(f"{BASE}/org/team-mood")["line"]


def test_relationship_labels_and_settings(tmp_path: Path) -> None:
    with hiring_client(tmp_path) as api:
        api.post(f"{BASE}/advance")
        rels = api.get(f"{BASE}/people/1/relationships")
        assert all(r["label"] in {"close", "good", "neutral", "strained", "hostile"} for r in rels)
        settings = api.get("/api/settings/llm")
        assert settings["budget_cents"] == 1000 and "key" not in {k.lower() for k in settings}
        assert settings["in_use"] == "Offline templates"  # no key in tests
        changed = api.client.put(
            "/api/settings/llm",
            json={
                "adapter": "templates",
                "monthly_budget_cents": 0,
                "model_events": "claude-haiku-5-5",
                "model_story": "claude-sonnet-5-5",
            },
        ).json()
        assert changed["adapter"] == "templates" and changed["budget_cents"] == 0
        assert api.get("/api/settings/llm")["budget_cents"] == 0
