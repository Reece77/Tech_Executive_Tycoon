"""M19 API (formulas.md 35): the Mines screen and its actions; founding a subsidiary and moving a
project into it; a mine's first sales; the critical events; the differential test (two mines
with the same revealed history but different hidden overruns and deposits give identical
responses); and no hidden value in a prompt (ADR-0005, ADR-0007)."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api import find_forbidden_keys
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.api.mining_views import mine_out, mines_out
from tst.config import Settings, get_settings
from tst.db.repository import ledger_balances, load_state, open_session
from tst.loader import LoadedData
from tst.sim.state import with_mine

TOOLS = Path(__file__).resolve().parents[3] / "tools"
BASE = "/api/saves/{}"


def _tools() -> Any:
    sys.path.insert(0, str(TOOLS))
    import e2e_m19_save

    return e2e_m19_save


@pytest.fixture
def saves(tmp_path: Path) -> Path:
    return tmp_path / "saves"


@pytest.fixture
def api(saves: Path) -> Iterator[Client]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as client:
        yield Client(client)


def test_found_a_subsidiary_and_move_a_project(
    api: Client, saves: Path, loaded: LoadedData
) -> None:
    path = _tools().holder(saves, "h", loaded)
    base = BASE.format("h")
    screen = api.get(f"{base}/mines")
    assert screen["mines"] == [] and [q["allowed"] for q in screen["quotes"]] == [True]
    out = api.post(
        f"{base}/mines/subsidiaries",
        json={"name": "Ironbark Mining", "region": "latin_america", "cents": 50_000_000_000},
    )
    sub = next(c for c in out["mines"]["companies"] if c["name"] == "Ironbark Mining")
    assert sub["role"] == "subsidiary" and sub["cash_cents"] == 50_000_000_000
    api.post(  # the name is taken
        f"{base}/mines/subsidiaries",
        json={"name": "ironbark mining", "region": "africa", "cents": 50_000_000_000},
        status=400,
    )
    project = next(a for a in out["mines"]["assets"] if a["kind"] == "project")
    out = api.post(
        f"{base}/mines/transfer", json={"to_company_id": sub["id"], "project_id": project["id"]}
    )
    moved = next(a for a in out["mines"]["assets"] if a["id"] == project["id"])
    assert moved["company_id"] == sub["id"]
    out = api.post(f"{base}/mines/build", json={"project_id": project["id"]})
    mine = out["mines"]["mines"][0]
    assert mine["company_id"] == sub["id"] and mine["status"] == "building"
    assert mine["revised_cents"] is None  # the overrun is hidden until the cost is revised
    with open_session(path) as session:
        books = ledger_balances(session)
    group_cash = sum(v for (c, a), v in books.items() if a == "1000_cash" and c in (1, sub["id"]))
    assert group_cash > 0
    assert sum(books.values()) == 0  # every posting balanced


def test_a_mine_ramps_up_and_sells(api: Client, saves: Path, loaded: LoadedData) -> None:
    _tools().building(saves, "b", loaded)
    base = BASE.format("b")
    mine = api.get(f"{base}/mines")["mines"][0]
    assert mine["status"] == "building" and mine["staff"] == mine["staff_needed"]
    api.post(f"{base}/advance")
    api.post(f"{base}/advance")
    mine = api.get(f"{base}/mines")["mines"][0]
    assert mine["status"] == "producing" and mine["revised_cents"] is not None
    assert mine["last_output_t"] > 0 and mine["history"][-1]["revenue_cents"] > 0
    assert mine["reserves_low_t"] < mine["reserves_high_t"]
    assert mine["price_usd_lb"] is not None and mine["cost_usd_lb"] is not None
    statements = api.get(f"{base}/finance/statements")  # the new accounts render
    assert statements is not None


@pytest.mark.parametrize(
    ("mode", "template", "choices"),
    [
        ("crash", "mine_price_crash", ["care", "hedge", "keep"]),
        ("accident", "mine_tailings_failure", ["investigate", "compensate", "contest"]),
    ],
)
def test_critical_mine_events(
    api: Client, saves: Path, loaded: LoadedData, mode: str, template: str, choices: list[str]
) -> None:
    path = getattr(_tools(), mode)(saves, mode, loaded)
    base = BASE.format(mode)
    events = api.get(f"{base}/events")
    open_ = [e for e in events["open"] if e["template_id"] == template]
    assert open_ and open_[0]["severity"] == "critical"
    assert events["blocking_event_id"] == open_[0]["event_id"]
    api.post(f"{base}/advance", status=409)  # a critical event blocks Continue
    with open_session(path) as session:
        state = load_state(session)
    event = next(e for e in state.events if e.template_id == template)
    assert [eff.stat for c in event.choices for eff in c.effects] == choices
    mine = api.get(f"{base}/mines")["mines"][0]
    assert mine["open_event"] == ("crash" if mode == "crash" else "accident")
    api.post(f"{base}/events/{open_[0]['event_id']}/choose", json={"choice": "A"})
    mine = api.get(f"{base}/mines")["mines"][0]
    assert mine["open_event"] is None
    if mode == "crash":
        assert mine["status"] == "care"


def test_differential_same_revealed_different_truth(saves: Path, loaded: LoadedData) -> None:
    """35.6, ADR-0007: two mines with the same revealed facts but different hidden overruns,
    tonnages, grades and recoveries look the same until the cost is revised and ore is mined;
    changing every hidden value of the whole save moves nothing on the screen."""
    path = _tools().building(saves, "diff", loaded)
    with open_session(path) as session:
        state = load_state(session)
        books = ledger_balances(session)
    mine = state.mines[0]
    fresh = replace(mine, revised_cents=None, capex_paid_cents=0, ready_turn=state.turn + 20)
    twin = replace(
        fresh,
        hidden_overrun=0.59,
        hidden_ore_mt=fresh.hidden_ore_mt * 3,
        hidden_grade=fresh.hidden_grade * 2,
        hidden_recovery=0.51,
    )
    a = mine_out(with_mine(state, fresh), fresh, loaded).model_dump()
    b = mine_out(with_mine(state, twin), twin, loaded).model_dump()
    assert a == b
    whole = mines_out(with_mine(state, fresh), books, loaded).model_dump()
    assert mines_out(with_mine(state, twin), books, loaded).model_dump() == whole
    assert find_forbidden_keys(whole) == []


def test_no_hidden_value_in_a_prompt(saves: Path, loaded: LoadedData) -> None:
    """ADR-0005: a mine event's prompt carries no overrun, tonnage, grade or recovery (planted
    unmistakable hidden values never appear)."""
    from tst.events.context import Kpis, build_prompt
    from tst.sim.events.director import eligible_targets

    path = _tools().accident(saves, "prompt", loaded)
    with open_session(path) as session:
        state = load_state(session)
    mine = state.mines[0]
    planted = replace(
        mine,
        hidden_overrun=0.4567891,
        hidden_ore_mt=87.654321,
        hidden_grade=0.0098765,
        hidden_recovery=0.7654321,
    )
    state = with_mine(state, planted)
    events = [e for e in state.events if (e.template_id or "").startswith("mine_")]
    assert events
    texts = []
    for event in events:
        template = loaded.game_data.event_template(event.template_id or "")
        system, user = build_prompt(
            state,
            event,
            template,
            eligible_targets(state, event),
            Kpis(10**9, None, 0, 1, 0),
            loaded.balance,
            loaded.game_data,
        )
        texts.append(system + user)
    joined = "\n".join(texts)
    for value in ("0.4567", "87.65", "0.0098", "0.7654"):
        assert value not in joined


def test_mines_survive_a_reload(saves: Path, loaded: LoadedData) -> None:
    path = _tools().building(saves, "reload", loaded)
    with open_session(path) as session:
        state = load_state(session)
    from tst.db.repository import run_turn

    run_turn(path, loaded)
    run_turn(path, loaded)
    with open_session(path) as session:
        after = load_state(session)
    assert len(after.mines) == len(state.mines) == 1
    m = after.mines[0]
    assert m.status == "producing" and m.history and m.history[-1].output_t > 0
    assert m.hidden_ore_mt == state.mines[0].hidden_ore_mt
