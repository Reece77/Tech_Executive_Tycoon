"""M33's API and hidden-value tests (docs/formulas.md 47.6; CLAUDE.md section 8). A save in
January 2028 with an open low-NA order of the player's (a distinctive hidden jitter) and a
running lithography stage (distinctive hidden work, overrun and success draw): the Equipment
route, the fab and order Explain and the Ask-why prompt show public facts and ranges only;
no allocation weight, place, jitter or programme draw is served or prompted."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.integration.test_api import find_forbidden_keys
from tests.integration.test_api_hiring import Client
from tst.advisor import ask
from tst.advisor.prompt import explain_prompt
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.equipment.models import Programme, ToolOrder

TURN = ym_to_turn(2028, 1)
JITTER = 0.7316245
WORK = 87.654321
OVERRUN = 0.4123987
SUCCESS = 0.2718281
HIDDEN = ("jitter", "success_u", "overrun", "work", "place", "weight", "history_months")


def _save(saves: Path, loaded: LoadedData) -> Path:
    path = create_save(
        "equipment", 7, "ex_big_tech_founders", company_name="Litho Co", data=loaded,
        save_dir=saves,
    )  # fmt: skip
    with open_session(path) as session:
        old = load_state(session)
        new = replace(old, turn=TURN)
        order = ToolOrder(
            900, "player", "euv_low", 12, TURN - 3, company_id=new.player.id, country="us",
            price_cents=19_000_000_000, jitter=JITTER,
        )  # fmt: skip
        prog = Programme(new.player.id, "litho_1", 1, TURN - 6, 1.1, WORK, OVERRUN, SUCCESS)
        new = replace(new, tool_orders=(order,), programmes=(prog,))
        sync_state(session, old, new)
        session.execute(text("UPDATE save_meta SET current_turn = :t"), {"t": TURN})
        session.commit()
    return path


def _clean(body: object) -> None:
    raw = json.dumps(body)
    for number in (JITTER, WORK, OVERRUN, SUCCESS):
        assert str(number) not in raw and f"{number:.4f}" not in raw, number
    for key in HIDDEN:
        assert f'"{key}"' not in raw, key
    assert find_forbidden_keys(body) == []


def test_equipment_route_and_hidden_values(tmp_path: Path, loaded: LoadedData) -> None:
    saves = tmp_path / "saves"
    path = _save(saves, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as c:
        api = Client(c)
        base = f"/api/saves/{path.name.removesuffix('.tst.sqlite')}"
        out = api.get(f"{base}/equipment")
        _clean(out)
        keys = [g["key"] for g in out["generations"]]
        assert keys == ["duv_immersion", "euv_low", "euv_high"]
        order = next(o for o in out["orders"] if o["id"] == 900)
        assert order["status"] == "open" and order["lead_label"]  # a range, in months
        assert order["prepay_cents"] > 0
        stage = next(s for s in out["programme"]["stages"] if s["key"] == "litho_1")
        assert stage["status"] == "running" and stage["end_window_label"]
        assert stage["throughput"] is None  # drawn only at success
        explain = api.get(f"{base}/explain/tool_wait?entity=900")
        _clean(explain)
        # rule errors come back as such
        bad = c.post(f"{base}/equipment/orders", json={"generation": "duv_immersion", "tools": 3})
        assert bad.status_code >= 400 and "queue" in bad.text
        china = c.post(f"{base}/equipment/litho/start", json={"stage": "litho_2", "funding": 1.0})
        assert china.status_code >= 400
    # the Ask-why prompt for the order's wait (ADR-0005): built from public items only
    found = ask.explained(path, loaded, "tool_wait", "900")
    state, kpis = ask._kpis(path, loaded)
    system, user = explain_prompt(
        state, found.explanation, kpis, found.template, found.speaker, "Why so long?", 80,
        loaded.game_data,
    )  # fmt: skip
    for number in (JITTER, WORK, OVERRUN, SUCCESS):
        assert f"{number:.3f}" not in system + user
