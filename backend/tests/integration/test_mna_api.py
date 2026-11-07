"""M14 API (formulas.md 28.8): targets, diligence, bids, deals and acquisitions over HTTP;
no hidden value in any response; and the differential test: two targets with the same
displayed range but different true values (and different hidden reservations) give the same
responses before diligence, errors included (as M12r finding 1)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import fund_save, move_save_directors, play_turn
from tests.integration.test_api import find_forbidden_keys
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData

SAVE = "deals"
BASE = f"/api/saves/{SAVE}"
CASH = 50_000_000_000_00  # $50B


def _build(
    save_dir: Path, loaded: LoadedData, mrr: int | None = None, personality: str | None = None
) -> Path:
    path = create_save(
        SAVE, 5, "funded_spinout", company_name="Kestrel", data=loaded, save_dir=save_dir
    )
    move_save_directors(path)
    fund_save(path, CASH)
    if mrr is not None or personality is not None:
        with open_session(path) as session, session.begin():
            before = load_state(session)
            zoho = next(c for c in before.companies if c.name == "Zoho")
            changed = replace(
                zoho,
                mrr_history=(mrr,) * 13 if mrr is not None else zoho.mrr_history,
                op_history=(mrr // 10,) * 13 if mrr is not None else zoho.op_history,
                personality=personality or zoho.personality,
            )
            state = replace(
                before, companies=tuple(changed if c.id == zoho.id else c for c in before.companies)
            )
            sync_state(session, before, state)
    return path


def _client(save_dir: Path) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    return TestClient(app)


@pytest.fixture
def api(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[TestClient, Path]]:
    save_dir = tmp_path / "saves"
    path = _build(save_dir, loaded)
    with _client(save_dir) as client:
        yield client, path


def _target(mna: dict[str, Any], name: str) -> dict[str, Any]:
    return next(t for t in mna["targets"] if t["name"] == name)


def test_targets_diligence_bid_and_close(api: tuple[TestClient, Path], loaded: LoadedData) -> None:
    client, path = api
    mna = client.get(f"{BASE}/mna").json()
    names = [t["name"] for t in mna["targets"]]
    assert names == sorted(names)  # by name, never by value
    zoho = _target(mna, "GitHub")
    assert zoho["listed"] is False and zoho["value_low_cents"] < zoho["value_high_cents"]
    assert zoho["findings"] == [] and zoho["people"] == [] and zoho["diligence"] == "none"
    assert all(p["quality_low"] is None for p in zoho["products"])
    big = _target(mna, "Zoho")  # 2026-11-05: over integration.max_staff, a brand only
    assert big["integrate_allowed"] is False and "too big to integrate" in big["integrate_note"]
    assert zoho["integrate_allowed"] is True and zoho["integrate_note"] is None
    salesforce = _target(mna, "Salesforce")
    assert salesforce["listed"] and salesforce["market_cap_cents"] > 0
    assert salesforce["value_low_cents"] is None
    out = client.post(f"{BASE}/mna/diligence", json={"company_id": zoho["company_id"]}).json()
    assert _target(out["mna"], "GitHub")["diligence"] == "under_way"
    for _ in range(2):
        play_turn(path, loaded)
    zoho = _target(client.get(f"{BASE}/mna").json(), "GitHub")
    assert zoho["diligence"] == "done" and zoho["people"]
    assert all(p["quality_low"] is not None for p in zoho["products"])
    low = zoho["value_low_cents"]
    bid = client.post(
        f"{BASE}/mna/offers", json={"company_id": zoho["company_id"], "price_cents": low // 4}
    )
    assert bid.status_code == 200 and "counters" in bid.json()["messages"][0]["title"]
    counter = _target(bid.json()["mna"], "GitHub")["counter_cents"]
    accepted = client.post(
        f"{BASE}/mna/offers",
        json={"company_id": zoho["company_id"], "price_cents": counter, "mode": "integrate"},
    ).json()
    (deal,) = accepted["mna"]["deals"]
    assert deal["status"] == "accepted" and deal["mode"] == "integrate"
    play_turn(path, loaded)
    after = client.get(f"{BASE}/mna").json()
    assert after["deals"][0]["status"] == "closed"
    (acq,) = after["acquisitions"]
    assert acq["mode"] == "integrate" and acq["pool_kept"] > 0 and acq["clash_months_left"] > 0
    assert "GitHub" not in [t["name"] for t in after["targets"]]
    for body in (mna, out, bid.json(), accepted, after):
        assert find_forbidden_keys(body) == []


def test_errors_name_no_hidden_number(api: tuple[TestClient, Path]) -> None:
    client, _ = api
    zoho = _target(client.get(f"{BASE}/mna").json(), "Zoho")["company_id"]
    hostile = client.post(
        f"{BASE}/mna/offers",
        json={"company_id": zoho, "price_cents": 10**9, "hostile": True, "mode": "brand"},
    )
    assert hostile.status_code == 400 and "listed target" in hostile.json()["message"]
    shares = client.post(
        f"{BASE}/mna/offers",
        json={"company_id": zoho, "price_cents": 10**9, "cash_share": 0.5, "mode": "brand"},
    )
    assert shares.status_code == 400 and "listed" in shares.json()["message"]


def _twin(tmp_path: Path, loaded: LoadedData, name: str, mrr: int, personality: str) -> TestClient:
    save_dir = tmp_path / name
    _build(save_dir, loaded, mrr=mrr, personality=personality)
    return _client(save_dir)


def test_same_displayed_range_same_responses(tmp_path: Path, loaded: LoadedData) -> None:
    """Zoho's true value and its hidden reservation premium differ between the two saves;
    its displayed range is the same, so every response before diligence is the same."""
    a = _twin(tmp_path, loaded, "a", 20_000_000_00, "premium")
    b = _twin(tmp_path, loaded, "b", 20_000_050_00, "cost_leader")
    with a, b:
        ma, mb = a.get(f"{BASE}/mna"), b.get(f"{BASE}/mna")
        za, zb = _target(ma.json(), "Zoho"), _target(mb.json(), "Zoho")
        assert (za["value_low_cents"], za["value_high_cents"]) == (
            zb["value_low_cents"],
            zb["value_high_cents"],
        )
        assert ma.text == mb.text
        zoho = za["company_id"]
        bodies: list[dict[str, Any]] = [
            {"company_id": zoho, "price_cents": 10**9, "hostile": True},
            {"company_id": zoho, "price_cents": 10**9, "cash_share": 0.5},
            {"company_id": zoho, "price_cents": CASH * 10},
            {"company_id": zoho, "price_cents": 0},
            {"company_id": 999, "price_cents": 10**9},
        ]
        for body in bodies:
            ra, rb = (
                a.post(f"{BASE}/mna/offers", json=body),
                b.post(f"{BASE}/mna/offers", json=body),
            )
            assert (ra.status_code, ra.text) == (rb.status_code, rb.text), body
        da = a.post(f"{BASE}/mna/diligence", json={"company_id": zoho})
        db = b.post(f"{BASE}/mna/diligence", json={"company_id": zoho})
        assert (da.status_code, da.text) == (db.status_code, db.text)
