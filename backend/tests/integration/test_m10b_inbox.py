"""M10b inbox (formulas.md 23.1): answered events archive themselves; read, unbookmarked items
older than inbox.auto_archive_months archive at month end; a bookmark keeps an item; open
major and critical events block the player's Continue (409 with the blocking events); Holiday
still answers a major event below its stop level with the first choice."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import answer_events, open_event
from tests.integration.test_api_hiring import BASE, hiring_client
from tst import holiday
from tst.db import repository
from tst.loader import LoadedData
from tst.sim.errors import CriticalEventOpenError


def _item(api, event_id: int) -> dict:  # type: ignore[no-untyped-def]
    return api.get(f"{BASE}/events/{event_id}/item")


def test_an_answered_event_archives_itself(tmp_path: Path, loaded: LoadedData) -> None:
    with hiring_client(tmp_path) as api:
        path = repository.save_path(tmp_path / "saves", "m1b")
        event_id = open_event(path, loaded, "quiet_tax_credit", severity="minor")
        assert _item(api, event_id)["archived"] is False
        api.post(f"{BASE}/events/{event_id}/choose", {"choice": "A"})
        assert _item(api, event_id)["archived"] is True
        inbox = api.get(f"{BASE}/inbox")["items"]
        assert event_id not in {i["link_id"] for i in inbox if i["link_kind"] == "event"}


def test_a_minor_event_answered_at_continue_archives(tmp_path: Path, loaded: LoadedData) -> None:
    with hiring_client(tmp_path) as api:
        path = repository.save_path(tmp_path / "saves", "m1b")
        event_id = open_event(path, loaded, "quiet_tax_credit", severity="minor")
        api.post(f"{BASE}/advance")
        assert _item(api, event_id)["archived"] is True


def test_major_events_block_continue(tmp_path: Path, loaded: LoadedData) -> None:
    with hiring_client(tmp_path) as api:
        path = repository.save_path(tmp_path / "saves", "m1b")
        first = open_event(path, loaded, "quiet_tax_credit", severity="major")
        second = open_event(path, loaded, "quiet_tax_credit", severity="major")
        events = api.get(f"{BASE}/events")
        assert sorted(events["blocking_event_ids"]) == sorted([first, second])
        assert events["blocking_event_id"] is None  # only a critical event opens the modal
        turn = api.get(f"{BASE}/overview")["turn"]
        blocked = api.post(f"{BASE}/advance", status=409)
        assert blocked["code"] == "events_open"
        assert sorted(blocked["event_ids"]) == sorted([first, second])
        assert "Answer 2 events first" in blocked["message"]
        assert api.get(f"{BASE}/overview")["turn"] == turn
        api.post(f"{BASE}/events/{first}/choose", {"choice": "A"})
        assert api.post(f"{BASE}/advance", status=409)["event_ids"] == [second]
        api.post(f"{BASE}/events/{second}/choose", {"choice": "A"})
        api.post(f"{BASE}/advance")
        assert api.get(f"{BASE}/overview")["turn"] == turn + 1


def test_holiday_answers_a_major_event_below_its_stop_level(
    tmp_path: Path, loaded: LoadedData
) -> None:
    with hiring_client(tmp_path) as api:
        path = repository.save_path(tmp_path / "saves", "m1b")
        event_id = open_event(path, loaded, "quiet_tax_credit", severity="major")
        with pytest.raises(CriticalEventOpenError):  # the player answers it before leaving
            holiday.check_start(path, loaded, 2, "critical")
        # During a holiday each month is an ordinary Continue that answers it (17.1).
        repository.run_turn(path, loaded)
        card = api.get(f"{BASE}/events/{event_id}")
        assert card["status"] == "auto" and card["chosen"] == "A"  # the first choice
        assert _item(api, event_id)["archived"] is True


def _plant(path: Path, n: int) -> list[int]:
    """n plain messages dated this month, as any turn writes them."""
    from tst.db.models import InboxItemRow

    with repository.write_session(path) as session:
        turn = repository.load_state(session).turn
        rows = [
            InboxItemRow(
                turn=turn,
                company_id=1,
                template="market_news",
                title=f"Note {k}",
                body="A note",
                read=False,
                archived=False,
                bookmarked=False,
            )
            for k in range(n)
        ]
        session.add_all(rows)
        session.flush()
        return [r.id for r in rows]


def test_old_read_items_archive_unless_bookmarked(tmp_path: Path, loaded: LoadedData) -> None:
    months = loaded.balance.inbox.auto_archive_months
    with hiring_client(tmp_path) as api:
        path = repository.save_path(tmp_path / "saves", "m1b")
        kept, read, unread = _plant(path, 3)
        api.post(f"{BASE}/inbox/{kept}/bookmark")
        api.post(f"{BASE}/inbox/{kept}/read")
        api.post(f"{BASE}/inbox/{read}/read")
        for month in range(months):
            answer_events(path, loaded)
            api.post(f"{BASE}/advance")
            if month < months - 1:  # younger than three months: still in the inbox
                inbox = {i["item_id"] for i in api.get(f"{BASE}/inbox?limit=500")["items"]}
                assert read in inbox
        archived = {i["item_id"] for i in api.get(f"{BASE}/inbox?limit=500&archived=true")["items"]}
        assert read in archived  # read, three months old: archived at month end
        inbox = {i["item_id"]: i for i in api.get(f"{BASE}/inbox?limit=500")["items"]}
        assert kept in inbox and inbox[kept]["bookmarked"] is True
        assert unread in inbox  # never read: stays
        assert api.post(f"{BASE}/inbox/{kept}/unbookmark")["bookmarked"] is False
