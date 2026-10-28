"""M4c: the inbox can be marked all read and cleaned by archiving; archived items can be found
again. None of it is a game action: no energy, nothing in decision_log."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from tests.integration.test_api_hiring import BASE, hiring_client
from tst.config import Settings
from tst.db import repository
from tst.db.models import DecisionLogRow


def test_mark_all_read_archive_and_find_again(tmp_path: Path) -> None:
    with hiring_client(tmp_path) as api:
        for role in ("designer", "software_engineer", "product_manager"):
            api.post(f"{BASE}/recruitment/searches", {"role": role, "channel": "network"}, 201)
        api.post(f"{BASE}/advance")
        energy = api.get(f"{BASE}/founder/energy")["energy"]
        inbox = api.get(f"{BASE}/inbox")
        assert inbox["unread"] >= 3 and all(not i["archived"] for i in inbox["items"])
        total = inbox["total"]

        first = inbox["items"][0]["item_id"]
        archived = api.post(f"{BASE}/inbox/{first}/archive")
        assert archived["archived"] and archived["read"]  # archiving reads it too
        assert api.get(f"{BASE}/inbox")["total"] == total - 1

        out = api.post(f"{BASE}/inbox/read-all")
        assert out == {"changed": inbox["unread"] - 1, "unread": 0}
        assert api.get(f"{BASE}/inbox?unread_only=true")["items"] == []

        out = api.post(f"{BASE}/inbox/archive-read")
        assert out["changed"] == total - 1 and out["unread"] == 0
        assert api.get(f"{BASE}/inbox")["items"] == []
        found = api.get(f"{BASE}/inbox?archived=true")
        assert found["total"] == total and all(i["archived"] for i in found["items"])
        assert api.get(f"{BASE}/overview")["latest_inbox"] == []

        back = api.post(f"{BASE}/inbox/{first}/unarchive")
        assert not back["archived"]
        assert [i["item_id"] for i in api.get(f"{BASE}/inbox")["items"]] == [first]
        api.post(f"{BASE}/inbox/999/archive", status=404)

        assert api.get(f"{BASE}/founder/energy")["energy"] == energy  # no energy
        path = repository.existing_save_path(
            Settings(save_dir=tmp_path / "saves").resolved_save_dir(), "m1b"
        )
        with repository.open_session(path) as session:
            kinds = session.scalars(select(DecisionLogRow.kind)).all()
            assert not any("inbox" in k or "archive" in k for k in kinds)
            assert session.scalar(select(func.count()).select_from(DecisionLogRow)) == len(kinds)
