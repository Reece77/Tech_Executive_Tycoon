"""Tooltips (M7b sub-task 4): the glossary route and the driver breakdowns the API builds.
The front end only displays them, so their sums must match the numbers they explain."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.test_api_hiring import BASE, hiring_client
from tests.integration.test_history import BASE as HISTORY_BASE
from tests.integration.test_history import SAVE as HISTORY_SAVE
from tst.api import breakdowns
from tst.loader import GlossaryFile, LoadedData


def test_glossary_route_serves_every_term(tmp_path: Path, loaded: LoadedData) -> None:
    with hiring_client(tmp_path) as api:
        terms = api.get("/api/meta/glossary")["terms"]
    assert terms == loaded.glossary
    assert "kpi.cash" in terms and "morale" in terms and "line.net" in terms


def test_glossary_is_validated() -> None:
    with pytest.raises(ValueError, match="lower-case"):
        GlossaryFile(terms={"Bad Key": "x"})
    with pytest.raises(ValueError, match="characters"):
        GlossaryFile(terms={"ok": ""})


def test_cash_and_burn_breakdowns_sum_to_last_months_change(tmp_path: Path) -> None:
    with hiring_client(tmp_path) as api:
        before = api.post(f"{BASE}/advance")["cash_cents"]
        after = api.post(f"{BASE}/advance")
        out = api.get(f"{BASE}/overview/breakdowns")
    change = after["cash_cents"] - before
    assert sum(i["amount"] for i in out["cash"]["items"]) == change
    assert {i["label"] for i in out["cash"]["items"]} <= set(breakdowns.CASH_ORDER)
    assert all(i["unit"] == "cents" for i in out["cash"]["items"])
    assert "Feb 2010" in out["cash"]["note"]
    assert sum(i["amount"] for i in out["burn"]["items"]) == -change
    assert after["monthly_burn_cents"] == max(-change, 0)
    runway = {i["label"]: i["amount"] for i in out["runway"]["items"]}
    assert runway["Cash"] == after["cash_cents"]
    assert (
        runway["Projected costs this month"] - runway["Projected revenue this month"]
        == (runway["Projected net burn"])
    )
    assert out["headcount"]["items"] == [{"label": "Company root", "amount": 1, "unit": "count"}]
    assert out["avg_morale"]["items"] == []  # the founder alone has no morale


def test_no_breakdowns_before_the_first_month(tmp_path: Path) -> None:
    with hiring_client(tmp_path) as api:
        out = api.get(f"{BASE}/overview/breakdowns")
    assert out["cash"]["items"] == [] and out["cash"]["note"] == "No month has closed yet."


@pytest.fixture
def history_api(built: Path):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    from tst.api.app import create_app
    from tst.config import Settings, get_settings

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=built.parent)
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def built(loaded: LoadedData, tmp_path_factory: pytest.TempPathFactory) -> Path:
    from tests.integration.test_history import _build

    return _build(loaded, tmp_path_factory.mktemp("tooltips"))


def test_staffed_company_breakdowns(history_api) -> None:  # type: ignore[no-untyped-def]
    base = f"/api/saves/{HISTORY_SAVE}"
    overview = history_api.get(f"{base}/overview").json()
    out = history_api.get(f"{base}/overview/breakdowns").json()
    staff = sum(i["amount"] for i in out["headcount"]["items"])
    assert staff == overview["headcount"]
    terms = out["avg_morale"]["items"]
    assert terms and {"Baseline", "Pay against the market rate"} <= {t["label"] for t in terms}
    assert "employees' morale terms" in out["avg_morale"]["note"]
    mrr = sum(i["amount"] for i in out["mrr"]["items"])
    assert mrr == overview["mrr_cents"]
    assert sum(i["amount"] for i in out["arr"]["items"]) == 12 * mrr
    (product,) = history_api.get(f"{base}/products").json()
    detail = history_api.get(f"{base}/products/{product['product_id']}").json()
    quality = detail["quality_breakdown"]
    assert quality["items"][0] == {
        "label": "Quality now",
        "amount": round(detail["quality"], 1),
        "unit": "points",
    }
    share = detail["segments"][0]["share_breakdown"]
    assert share["items"][0]["unit"] == "percent" and "weighs quality" in share["note"]
    person = next(p for p in history_api.get(f"{base}/people").json() if not p["is_founder"])
    profile = history_api.get(f"{base}/people/{person['person_id']}").json()
    salary = profile["employment"]["salary_breakdown"]
    assert [i["label"] for i in salary["items"]] == ["Salary", "Market rate", "Difference"]
    assert "market rate" in salary["note"]
    assert HISTORY_BASE.startswith(base)
