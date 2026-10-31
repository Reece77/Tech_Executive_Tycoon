"""M7c playtest bug: the Overview's monthly burn left out an event paid by answering it before
Continue, so the tile disagreed with its own breakdown and the P&L (Nov 2011: $86,530 shown,
cash fell $87,710)."""

from __future__ import annotations

from pathlib import Path

from tests.helpers import open_event
from tests.integration.test_api_hiring import BASE, hiring_client
from tst.config import Settings
from tst.db.repository import existing_save_path
from tst.loader import LoadedData


def test_burn_counts_an_event_paid_before_continue(tmp_path: Path, loaded: LoadedData) -> None:
    with hiring_client(tmp_path) as api:
        before = api.post(f"{BASE}/advance")["cash_cents"]
        path = existing_save_path(Settings(save_dir=tmp_path / "saves").resolved_save_dir(), "m1b")
        event_id = open_event(path, loaded, "milestone_case_study", severity="minor")
        paid = api.post(f"{BASE}/events/{event_id}/choose", {"choice": "A"})
        assert paid["event"]["chosen"] == "A"
        mid = api.get(f"{BASE}/overview")["cash_cents"]
        assert mid < before  # the trade cost cash at once
        after = api.post(f"{BASE}/advance")
        out = api.get(f"{BASE}/overview/breakdowns")
    fall = before - after["cash_cents"]
    assert sum(i["amount"] for i in out["burn"]["items"]) == fall
    assert after["monthly_burn_cents"] == fall


def test_the_burn_notes_projection_is_net_of_revenue(tmp_path: Path) -> None:
    """The burn tile's note showed this month's gross costs beside last month's net burn
    (Dec 2013: "Dec projected $214,140" under $96,577); it now projects the net burn."""
    with hiring_client(tmp_path) as api:
        api.post(f"{BASE}/advance")
        ov = api.get(f"{BASE}/overview")
    net = ov["month_total_cents"] - ov["month_revenue_cents"]
    assert ov["month_net_burn_cents"] == max(net, 0) > 0
