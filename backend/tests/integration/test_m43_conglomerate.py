"""M43 sub-task 2: the conglomerate view's route on a group (a holding company over an operating
company and two kept brands, tools/e2e_m16_save.py) and the January letter to shareholders on a
new game played through its first December. No response carries a hidden field (ADR-0007), and
the figures add up to the group's."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api import find_forbidden_keys
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.repository import create_save, run_turn
from tst.llm.offline import MockLLMAdapter
from tst.loader import LoadedData

TOOLS = Path(__file__).resolve().parents[3] / "tools"
SAVE = "conglomerate"
BASE = f"/api/saves/{SAVE}"


@pytest.fixture
def api(tmp_path: Path, loaded: LoadedData) -> Iterator[Client]:
    sys.path.insert(0, str(TOOLS))
    from e2e_m16_save import formed

    save_dir = tmp_path / "saves"
    formed(save_dir, SAVE, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client)


def test_the_group_by_industry_and_company(api: Client) -> None:
    out = api.get(f"{BASE}/conglomerate")
    assert find_forbidden_keys(out) == []
    roles = [c["role"] for c in out["companies"]]
    assert roles[0] == "holding" and "operating" in roles and roles.count("subsidiary") == 2
    assert out["industries"], "the group reports at least one industry"
    revenue = sum(i["figures"]["revenue_cents"] for i in out["industries"])
    corporate = out["corporate"]["revenue_cents"] if out["corporate"] else 0
    assert revenue + corporate == out["group"]["revenue_cents"]
    profit = sum(i["figures"]["operating_profit_cents"] for i in out["industries"])
    corporate_profit = out["corporate"]["operating_profit_cents"] if out["corporate"] else 0
    assert profit + corporate_profit == out["group"]["operating_profit_cents"]
    assert sum(i["share_of_revenue"] for i in out["industries"]) == pytest.approx(
        revenue / out["group"]["revenue_cents"]
    )
    for i in out["industries"]:
        assert i["risk"] in ("low", "moderate", "high", "new")
        assert len(i["trend"]) <= 10 + 1  # ten years and this one
    assert {a["key"] for a in out["allocation"]} == {i["key"] for i in out["industries"]}
    assert all(p["kind"] in ("pitch", "group_pitch", "proposal") for p in out["proposals"])


def test_a_january_letter_each_year_kept_in_history(tmp_path: Path, loaded: LoadedData) -> None:
    saves = tmp_path / "saves"
    path = create_save(
        "letter", 7, "funded_spinout", company_name="Letter Co", data=loaded, save_dir=saves
    )
    adapter = MockLLMAdapter()
    for _ in range(12):  # January to December 2010: December's turn queues the letter
        run_turn(path, loaded, adapter=adapter)
    letters = [c for c in adapter.calls if c.kind == "letter"]
    assert len(letters) == 1 and "Dear shareholders" in letters[0].user
    assert "2010" in letters[0].user
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as raw:
        client = Client(raw)
        out = client.get("/api/saves/letter/conglomerate")
        assert [(x["year"], x["turn"]) for x in out["letters"]] == [(2010, 12)]
        assert out["letters"][0]["text"].startswith("Dear shareholders")
        assert out["letters"][0]["source"] == "mock"
        timeline = client.get("/api/saves/letter/history/timeline")
        titles = [r["title"] for r in timeline["rows"]]
        assert "Letter to shareholders, 2010" in titles
