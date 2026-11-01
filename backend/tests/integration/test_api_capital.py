"""M10 API (docs/formulas.md 20.4): loans with schedule and covenant headroom, taking and
repaying a loan, and the macro strip, which never carries a month ahead of the one the player
is in. The Client checks every response for hidden fields."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.repository import create_save, load_state, open_session, run_turn
from tst.db.state_io import read_meta, sync_state
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.finance import macro
from tst.sim.rng import RngFactory

SAVE = "cap"
BASE = f"/api/saves/{SAVE}"


@pytest.fixture
def setup(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[Client, Path]]:
    save_dir = tmp_path / "saves"
    path = create_save(
        SAVE, 5, "funded_spinout", company_name="Cap Co", data=loaded, save_dir=save_dir
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client), path


def test_take_a_loan_see_the_schedule_and_repay(
    setup: tuple[Client, Path], loaded: LoadedData
) -> None:
    api, path = setup
    out = api.get(f"{BASE}/finance/loans")
    assert out["loans"] == []
    venture = next(o for o in out["offers"] if o["instrument"] == "venture_debt")
    bank = next(o for o in out["offers"] if o["instrument"] == "bank_loan")
    assert venture["eligible"] and venture["lender"] == "Silicon Valley Bank"
    assert not bank["eligible"] and "stage 3" in bank["problem"]
    preview = api.post(
        f"{BASE}/finance/loans/preview",
        {"instrument": "venture_debt", "amount_cents": venture["max_cents"]},
    )
    assert preview["problem"] is None and preview["first_payment"]["principal_cents"] == 0
    assert preview["warrant_shares"] > 0
    api.post(
        f"{BASE}/finance/loans",
        {"instrument": "venture_debt", "amount_cents": venture["max_cents"]},
        status=201,
    )
    run_turn(path, loaded)
    loans = api.get(f"{BASE}/finance/loans")
    loan = loans["loans"][0]
    assert loan["balance_cents"] == venture["max_cents"] == loans["debt_cents"]
    assert len(loan["schedule"]) == 35 and loan["schedule"][-1]["balance_after_cents"] == 0
    assert loan["covenants"][0]["holds"] and loan["interest_paid_cents"] > 0
    api.post(f"{BASE}/finance/loans/{loan['id']}/repay", {"amount_cents": 1_000_000})
    api.post(f"{BASE}/finance/loans/{loan['id']}/repay", {})
    after = api.get(f"{BASE}/finance/loans")["loans"][0]
    assert after["status"] == "repaid" and after["balance_cents"] == 0
    api.post(
        f"{BASE}/finance/loans", {"instrument": "bank_loan", "amount_cents": 10**8}, status=400
    )


def test_macro_shows_history_up_to_now_and_never_ahead(
    setup: tuple[Client, Path], loaded: LoadedData
) -> None:
    api, path = setup
    for _ in range(3):
        run_turn(path, loaded)
    out = api.get(f"{BASE}/finance/macro")
    assert out["current"]["label"] == "Apr 2010" and not out["after_history"]
    assert [m["label"] for m in out["months"]][-4:] == [
        "Jan 2010",
        "Feb 2010",
        "Mar 2010",
        "Apr 2010",
    ]
    assert {i["key"] for i in out["indicators"]} == {
        "base_rate",
        "climate",
        "confidence",
        "ai_index",
    }
    assert out["current"]["base_rate"] == 0.2  # April 2010's fed funds rate, not a later one


def _jump_past_history(path: Path, loaded: LoadedData, to_turn: int) -> list[macro.MacroMonth]:
    """Write the save as if played to `to_turn`, with every macro month before it."""
    rng = RngFactory(5)
    months: list[macro.MacroMonth] = []
    prev = None
    for turn in range(to_turn):
        prev = macro.month_for(turn, prev, rng, loaded.balance, loaded.game_data)
        months.append(prev)
    with open_session(path) as session:
        old = load_state(session)
        new = old
        for m in months:  # one row per month, as phase 1 writes them
            nxt = replace(new, macro=m)
            sync_state(session, new, nxt)
            new = nxt
        read_meta(session).current_turn = to_turn
        session.commit()
    return months


def test_no_future_macro_value_after_2025(setup: tuple[Client, Path], loaded: LoadedData) -> None:
    api, path = setup
    now = ym_to_turn(2027, 6)
    months = _jump_past_history(path, loaded, now)
    out = api.get(f"{BASE}/finance/macro")
    assert out["after_history"]
    assert out["current"]["turn"] == now - 1  # June 2027 is drawn at its Continue, not before
    assert max(m["turn"] for m in out["months"]) == now - 1
    assert out["current"]["climate"] == round(months[-1].climate, 4)
    ahead = macro.month_for(now, months[-1], RngFactory(5), loaded.balance, loaded.game_data)
    text = json.dumps(out)
    for value in (ahead.base_rate, ahead.climate, ahead.confidence):
        assert str(round(value, 4)) not in text
