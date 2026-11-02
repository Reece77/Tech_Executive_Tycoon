"""The spec's v1 acceptance (M7b sub-task 7): a new game played for 120 months through the API
with Holiday and the M3a earn-and-burn decisions. Critical events get their first choice;
every GET route is opened each year; no response may be a 5xx; the ledger balances; and a
reload (a new app, nothing remembered) returns exactly what the API returned before it."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from tests.balance_scripts import EARN_AND_BURN_PRICES, MARKETING_CENTS
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db import migrate, repository
from tst.db.models import LedgerEntryRow, LedgerLineRow
from tst.db.session import forget_engine

SAVE = "decade"
BASE = f"/api/saves/{SAVE}"
MONTHS = 120
YEAR = 12
HOLIDAY = 12  # months per holiday once the product is live
ENGINEERS = 3
GO_TO_MARKET = ("account_executive", "marketer")
OFFER_RATIO = 1.2  # offers at 1.2 x the ask, as the golden script


class Api:
    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.calls = 0

    def call(self, method: str, url: str, json: Any = None) -> tuple[int, Any]:
        res = self.client.request(method, url, json=json)
        self.calls += 1
        assert res.status_code < 500, (method, url, res.status_code, res.text)
        return res.status_code, res.json() if res.content else None

    def get(self, url: str) -> Any:
        status, body = self.call("GET", url)
        assert status == 200, (url, status, body)
        return body

    def post(self, url: str, json: Any = None) -> tuple[int, Any]:
        return self.call("POST", url, json)


def _app(save_dir: Path) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    return TestClient(app)


def _answer_critical(api: Api) -> None:
    """Every blocking event first: major ones block Continue and Holiday too (23.1, M10b)."""
    for blocking in api.get(f"{BASE}/events")["blocking_event_ids"]:
        status, _ = api.post(f"{BASE}/events/{blocking}/choose", {"choice": "A"})
        assert status == 200


def _hire_from(api: Api, role: str, count: int) -> None:
    """Interview and offer to the open candidates for a role while energy lasts."""
    made = 0
    for c in api.get(f"{BASE}/recruitment/candidates"):
        if made >= count or c["role"] != role or c["candidacy"].get("pending_offer"):
            continue
        if api.post(f"{BASE}/recruitment/candidates/{c['person_id']}/interview")[0] != 200:
            break  # out of energy this month
        ask = c["candidacy"]["salary_expectation_cents"]
        offer = {"salary_cents": int(ask * OFFER_RATIO), "equity_bp": 0}
        if api.post(f"{BASE}/recruitment/candidates/{c['person_id']}/offer", offer)[0] == 200:
            made += 1


def _route_urls(api: Api) -> list[str]:
    """Every GET route, with ids from what the save holds (one of each)."""
    spec = api.client.get("/openapi.json").json()
    people = api.get(f"{BASE}/people")
    products = api.get(f"{BASE}/products")
    rivals = api.get(f"{BASE}/rivals")
    events = api.get(f"{BASE}/events")
    inbox = api.get(f"{BASE}/inbox")["items"]
    left = api.get(f"{BASE}/history/hall-of-fame")["notable_departures"]
    ids = {
        "save_id": SAVE,
        "person_id": next((p["person_id"] for p in people if not p["is_founder"]), None),
        "product_id": products[0]["product_id"] if products else None,
        "category": "b2b_saas",
        "company_id": rivals["rivals"][0]["company_id"] if rivals.get("rivals") else None,
        "event_id": (events["open"] + events["recent"])[0]["event_id"]
        if events["open"] + events["recent"]
        else None,
        "sheet_id": None,  # previews need an open round; covered by the finance tests
        "item_id": inbox[0]["item_id"] if inbox else None,
    }
    former = left[0]["person_id"] if left else None  # /people/{id}/former is for leavers (M7c)
    urls = []
    for path, ops in spec["paths"].items():
        if "get" not in ops:
            continue
        names = re.findall(r"\{(\w+)\}", path)
        values = {**ids, "person_id": former} if path.endswith("/former") else ids
        if any(values.get(n) is None for n in names):
            continue
        url = path
        for n in names:
            url = url.replace(f"{{{n}}}", str(values[n]))
        urls.append(url)
    for period in ("month", "quarter", "year"):
        urls.append(f"{BASE}/finance/statements?period={period}")
    urls.append(f"{BASE}/history/timeline?search=a&limit=500")
    return urls


def _open_every_screen(api: Api) -> dict[str, Any]:
    return {url: api.get(url) for url in _route_urls(api)}


def _wait_for_holiday(api: Api) -> dict[str, Any]:
    for _ in range(6000):
        body = api.get(f"{BASE}/holiday")
        if body["status"] != "running":
            return dict(body)
        time.sleep(0.02)
    raise AssertionError("the holiday did not finish")


@pytest.mark.nightly  # about a minute: v1's full-length acceptance run (M7b)
def test_a_ten_year_run_through_the_api(tmp_path: Path) -> None:
    with _app(tmp_path) as client:
        api = Api(client)
        status, _ = api.post(
            "/api/saves",
            {
                "name": SAVE,
                "seed": 7,
                "scenario": "funded_spinout",
                "company_name": "Decade Co",
                "mission": ["ai", "enterprise"],
            },
        )
        assert status == 201
        api.post(
            f"{BASE}/recruitment/searches", {"role": "software_engineer", "channel": "job_post"}
        )
        _, product = api.post(
            f"{BASE}/products",
            {"name": "Pipeline", "category": "b2b_saas", "segments": list(EARN_AND_BURN_PRICES)},
        )
        pid = product["product"]["product_id"] if "product" in product else product["product_id"]
        for segment, price in EARN_AND_BURN_PRICES.items():
            api.post(f"{BASE}/products/{pid}/price", {"segment": segment, "price_cents": price})
        api.post(f"{BASE}/products/{pid}/assign", {"unit_id": None})
        api.post(f"{BASE}/products/{pid}/marketing", {"budget_cents": MARKETING_CENTS})

        holidays = 0
        reasons: list[str] = []
        snapshots: dict[str, Any] = {}
        while (overview := api.get(f"{BASE}/overview"))["turn"] < MONTHS:
            turn = overview["turn"]
            if overview["game_state"] != "active":
                break
            if turn % YEAR == 0:
                snapshots = _open_every_screen(api)
            _answer_critical(api)
            live = api.get(f"{BASE}/products/{pid}")
            if live["status"] == "in_development":
                if live["launch"]["ready"]:
                    assert api.post(f"{BASE}/products/{pid}/launch")[0] == 200
                if turn == 1:
                    _hire_from(api, "software_engineer", ENGINEERS)
                    for role in GO_TO_MARKET:
                        api.post(
                            f"{BASE}/recruitment/searches", {"role": role, "channel": "network"}
                        )
                if turn == 2:
                    for role in GO_TO_MARKET:
                        _hire_from(api, role, 1)
                assert api.post(f"{BASE}/advance")[0] == 200
                continue
            months = min(HOLIDAY, MONTHS - turn, YEAR - turn % YEAR)
            status, body = api.post(f"{BASE}/holiday", {"months": months, "stop": "critical"})
            assert status == 202, body
            done = _wait_for_holiday(api)
            assert done["status"] == "finished", done
            holidays += 1
            reasons.append(done["reason"])

        final = api.get(f"{BASE}/overview")
        assert final["turn"] == MONTHS or final["game_state"] != "active", final["turn"]
        assert final["turn"] >= MONTHS, f"the company ended at turn {final['turn']}"
        assert holidays >= 5 and "months" in reasons
        hires = api.get(f"{BASE}/history/timeline?search=accepted%20your%20offer&limit=500")
        hired = [r for r in hires["rows"] if r["kind"] == "entry"]
        assert len(hired) >= ENGINEERS, len(hired)  # the script hired (some later left)
        launched = api.get(f"{BASE}/products/{pid}")
        assert launched["status"] != "in_development" and launched["launched_turn"] is not None
        print(
            f"10-year run: turn {final['turn']}, ARR {final['arr_cents'] / 100:,.0f},"
            f" cash {final['cash_cents'] / 100:,.0f}, staff {final['headcount']}"
            f" ({len(hired)} hired),"
            f" launched {launched['launched_label']}, {holidays} holidays {reasons},"
            f" {api.calls} calls"
        )
        snapshots = _open_every_screen(api)
        assert len(snapshots) > 40 and api.calls > 1000

    path = repository.save_path(tmp_path, SAVE)
    with repository.open_session(path) as session:
        unbalanced = session.execute(
            select(LedgerLineRow.entry_id)
            .group_by(LedgerLineRow.entry_id)
            .having(func.sum(LedgerLineRow.amount_cents) != 0)
        ).all()
        entries = session.scalar(select(func.count()).select_from(LedgerEntryRow))
        total = session.scalar(select(func.sum(LedgerLineRow.amount_cents)))
    assert unbalanced == [] and entries and total == 0

    # A reload: forget everything this process remembers, then read every route again.
    repository._LAST.clear()
    forget_engine(path)
    migrate.forget(path)
    with _app(tmp_path) as client:
        again = {url: Api(client).get(url) for url in snapshots}
    assert again == snapshots
