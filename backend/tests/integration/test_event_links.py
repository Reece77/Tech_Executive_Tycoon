"""M7c sub-task 2: event deep links. An event's own inbox message is found by event id, any
message opens by id wherever it falls in the pages, an answered event older than the live
state's 24 months still opens its card, and a holiday summary links the events it lists."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from tests.helpers import open_event
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.models import EventRow, InboxEventLinkRow, SaveMetaRow
from tst.db.repository import create_save, open_session, run_action
from tst.holiday import Vitals, write_summary
from tst.loader import LoadedData
from tst.sim.actions import ChooseEvent

SAVE = "links"
BASE = f"/api/saves/{SAVE}"


@pytest.fixture
def setup(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[Client, Path, int]]:
    save_dir = tmp_path / "saves"
    path = create_save(
        SAVE, 6, "funded_spinout", company_name="Links Co", data=loaded, save_dir=save_dir
    )
    event_id = open_event(path, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client), path, event_id


def test_event_item_and_single_item(setup: tuple[Client, Path, int], loaded: LoadedData) -> None:
    client, path, event_id = setup
    item = client.get(f"{BASE}/events/{event_id}/item")
    assert item["link_kind"] == "event" and item["link_id"] == event_id
    assert client.get(f"{BASE}/inbox/{item['item_id']}") == item
    client.get(f"{BASE}/inbox/99999", status=404)
    client.get(f"{BASE}/events/99999/item", status=404)
    event = client.get(f"{BASE}/events/{event_id}")
    run_action(path, loaded, ChooseEvent(1, event_id, event["choices"][-1]["key"]))
    answered = client.get(f"{BASE}/events/{event_id}")
    assert answered["status"] == "answered" and answered["chosen"] == event["choices"][-1]["key"]


def test_an_old_answered_event_still_opens(
    setup: tuple[Client, Path, int], loaded: LoadedData
) -> None:
    """The live state keeps 24 months of events; an older one is read from its row."""
    client, path, event_id = setup
    choice = client.get(f"{BASE}/events/{event_id}")["choices"][0]["key"]
    run_action(path, loaded, ChooseEvent(1, event_id, choice))
    with open_session(path) as session, session.begin():
        session.execute(update(SaveMetaRow).values(current_turn=40))
    out = client.get(f"{BASE}/events/{event_id}")
    assert out["event_id"] == event_id and out["chosen"] == choice


def test_holiday_summary_links_its_events(
    setup: tuple[Client, Path, int], loaded: LoadedData
) -> None:
    client, path, event_id = setup
    with open_session(path) as session, session.begin():
        session.execute(
            update(EventRow)
            .where(EventRow.id == event_id)
            .values(status="auto", chosen="A", resolved_turn=0)
        )
    vitals = Vitals(
        turn=0, cash_cents=0, arr_cents=0, headcount=1, avg_morale=None, runway_months=None
    )
    item_id = write_summary(path, loaded, 1, "months", vitals, replace(vitals, turn=1))
    with open_session(path) as session:
        assert session.get(InboxEventLinkRow, (item_id, 0)) is not None
    item = client.get(f"{BASE}/inbox/{item_id}")
    assert [e["event_id"] for e in item["event_links"]] == [event_id]
