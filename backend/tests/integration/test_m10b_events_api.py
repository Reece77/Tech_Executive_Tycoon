"""M10b events with visible, lasting effects through the API (formulas.md 23.2): choices as
numbers, a modifier on the active-effects panels, energy effects in the energy tooltip, and
the month-end "Your choices this month" line."""

from __future__ import annotations

from pathlib import Path

from tests.helpers import open_event
from tests.integration.test_api_hiring import BASE, hiring_client
from tst.db import repository
from tst.loader import LoadedData


def test_a_modifier_shows_runs_and_is_reported(tmp_path: Path, loaded: LoadedData) -> None:
    with hiring_client(tmp_path) as api:
        path = repository.save_path(tmp_path / "saves", "m1b")
        event_id = open_event(path, loaded, "early_mentor_offer", severity="minor")
        card = api.get(f"{BASE}/events/{event_id}")
        a, b = card["choices"]
        assert a["effects"] == [
            "+2 founder energy next month",
            "+5% founder energy each month for 6 months",
        ]
        assert b["effects"] == ["Do nothing: no effect"] and b["do_nothing"] is True
        api.post(f"{BASE}/events/{event_id}/choose", {"choice": "A"})
        (effect,) = api.get(f"{BASE}/overview")["active_effects"]
        assert effect["event_id"] == event_id and effect["months_left"] == 6
        assert effect["text"] == "+5% founder energy each month for 6 months"
        founder = api.get(f"{BASE}/people/1")
        assert [e["modifier_id"] for e in founder["active_effects"]] == [effect["modifier_id"]]
        energy = api.get(f"{BASE}/founder/energy")
        assert energy["max"] == 63  # 60 x 1.05
        assert any(a["percent"] and "6 months left" in a["label"] for a in energy["adjustments"])
        api.post(f"{BASE}/advance")
        energy = api.get(f"{BASE}/founder/energy")
        assert any(a["label"].startswith("+2 from ") for a in energy["adjustments"])
        assert api.get(f"{BASE}/overview")["active_effects"][0]["months_left"] == 5
        inbox = api.get(f"{BASE}/inbox?limit=200")["items"]
        line = next(i for i in inbox if i["kind"] == "choices_month")
        assert line["title"] == "Your choices this month"
        assert "+2 founder energy next month" in line["body"]
        assert "Started: +5% founder energy each month for 6 months" in line["body"]
