"""M16 API (formulas.md 31.2, 31.10): the Group screen, forming the holding company, and the
company switcher on the finance screens. No response carries a hidden field (ADR-0007)."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.loader import LoadedData

TOOLS = Path(__file__).resolve().parents[3] / "tools"
SAVE = "group"
BASE = f"/api/saves/{SAVE}"


@pytest.fixture
def api(tmp_path: Path, loaded: LoadedData) -> Iterator[Client]:
    sys.path.insert(0, str(TOOLS))
    from e2e_m16_save import eligible

    save_dir = tmp_path / "saves"
    eligible(save_dir, SAVE, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client)


def test_group_screen_form_and_switcher(api: Client) -> None:
    before = api.get(f"{BASE}/group")
    assert not before["formed"] and before["can_form"] and before["reasons"] == []
    assert before["form_fee_cents"] > 0
    roles = [e["role"] for e in before["entities"]]
    assert roles == ["operating", "subsidiary", "subsidiary"]
    assert all(e["treatment"] == "consolidated" for e in before["entities"][1:])
    assert all(e["value_low_cents"] <= e["value_high_cents"] for e in before["entities"][1:])
    cap_before = api.get(f"{BASE}/finance/captable")

    out = api.post(f"{BASE}/group/form")
    group = out["group"]
    assert group["formed"] and not group["can_form"]
    tree = group["entities"]
    assert [e["role"] for e in tree] == ["holding", "operating", "subsidiary", "subsidiary"]
    holding = tree[0]
    assert holding["listed"] and holding["market_cap_cents"] > 0
    assert all(e["parent_id"] == holding["company_id"] and e["depth"] == 1 for e in tree[1:])
    assert all(e["stake_bp"] == 10_000 for e in tree[1:])
    api.post(f"{BASE}/group/form", status=400)  # once only

    # the cap table moved: the default is the listed holding company's
    cap = api.get(f"{BASE}/finance/captable")
    founder = [h for h in cap["holders"] if h["is_founder"]]
    old = [h for h in cap_before["holders"] if h["is_founder"]]
    assert founder and founder[0]["shares"] == old[0]["shares"]
    operating = api.get(f"{BASE}/finance/captable?company_id=1")
    assert any(h["holder"] == holding["name"] for h in operating["holders"])
    assert api.get(f"{BASE}/finance/board")["seats"]
    # the switcher: one company's statements, or the group's (the default)
    one = api.get(f"{BASE}/finance/statements?company_id={tree[2]['company_id']}")
    assert not one["consolidated"]
    whole = api.get(f"{BASE}/finance/statements")
    assert whole["consolidated"] and len(whole["subsidiaries"]) == 3
    api.get(f"{BASE}/finance/statements?company_id=999999", status=404)
    api.post(f"{BASE}/advance")
    after = api.get(f"{BASE}/finance/statements")
    last = after["periods"][-1]["balance_sheet"]
    assert last["total_assets_cents"] == last["total_liabilities_and_equity_cents"]
