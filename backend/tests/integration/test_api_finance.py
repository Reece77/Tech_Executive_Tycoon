"""M4a API: statements, the cap table, SAFEs and the hint band, priced rounds with the
dilution preview, the board, the runway and game over. Every response is checked for hidden
fields and the formulas.md 14.9 forbidden names (the Client does it)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.repository import create_save, load_state, open_session, run_turn
from tst.db.state_io import sync_state
from tst.loader import LoadedData

SAVE = "fin"
BASE = f"/api/saves/{SAVE}"


@pytest.fixture
def setup(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[Client, Path]]:
    save_dir = tmp_path / "saves"
    # Seed 16: several firms answer this garage's seed round (see test_fundraising).
    path = create_save(
        SAVE, 16, "garage_bootstrap", company_name="Fin Co", data=loaded, save_dir=save_dir
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client), path


def test_statements_reconcile_by_period(setup: tuple[Client, Path], loaded: LoadedData) -> None:
    api, path = setup
    assert api.get(f"{BASE}/finance/statements")["periods"] == []  # nothing closed yet
    for _ in range(4):
        run_turn(path, loaded)
    months = api.get(f"{BASE}/finance/statements?period=month")["periods"]
    assert [p["label"] for p in months] == ["Jan 2010", "Feb 2010", "Mar 2010", "Apr 2010"]
    for p in months:
        sheet, flow = p["balance_sheet"], p["cash_flow"]
        assert sheet["total_assets_cents"] == sheet["total_liabilities_and_equity_cents"]
        assert (
            flow["operating_cents"] + flow["investing_cents"] + flow["financing_cents"]
            == (flow["change_in_cash_cents"])
        )
        assert flow["operating_cents"] == p["profit_and_loss"]["net_result_cents"]
        pnl = p["profit_and_loss"]  # M4b totals: the front end never sums
        opex = sum(x["amount_cents"] for x in pnl["operating_expenses"])
        assert pnl["total_operating_expenses_cents"] == opex
        assert pnl["gross_margin_cents"] - opex == pnl["operating_result_cents"]
        assert flow["burn_cents"] == max(0, -flow["operating_cents"])
        assert sheet["total_liabilities_cents"] == sum(
            x["amount_cents"] for x in sheet["liabilities"]
        )
    quarters = api.get(f"{BASE}/finance/statements?period=quarter")["periods"]
    assert [(q["label"], q["complete"]) for q in quarters] == [
        ("Q1 2010", True),
        ("Q2 2010", False),
    ]
    jan = months[0]["profit_and_loss"]
    assert [x["account"] for x in jan["operating_expenses"]] == ["6100_rent", "6900_general_admin"]
    assert api.get(f"{BASE}/finance/statements?period=decade", status=422)


def test_safe_round_and_preview_through_the_api(
    setup: tuple[Client, Path], loaded: LoadedData
) -> None:
    api, path = setup
    cap = api.get(f"{BASE}/finance/captable")
    assert cap["fd_shares"] == 10_000_000 and cap["share_price_dollars"] == "0"
    assert [(h["holder_kind"], h["shares"]) for h in cap["holders"]] == [
        ("person", 9_000_000),
        ("pool", 1_000_000),
    ]
    hint = api.post(
        f"{BASE}/finance/safes/hint", {"amount_cents": 30_000_000, "cap_cents": 100_000_000}
    )
    assert (hint["hint"], hint["fraction"], hint["problems"], hint["energy_cost"]) == (
        "likely",
        0.3,
        [],
        10,
    )
    far = api.post(
        f"{BASE}/finance/safes/hint", {"amount_cents": 1_000, "cap_cents": 5_000_000_000}
    )
    assert far["hint"] == "unlikely" and far["problems"]
    out = api.post(
        f"{BASE}/finance/safes", {"amount_cents": 30_000_000, "cap_cents": 100_000_000}, 201
    )
    assert out["energy"]["energy"] == 50
    assert api.get(f"{BASE}/finance/safes")["open"] is True
    run_turn(path, loaded)
    (safe,) = api.get(f"{BASE}/finance/safes")["safes"]
    assert (safe["status"], safe["fraction"]) == ("outstanding", 0.3)

    rounds = api.get(f"{BASE}/finance/rounds")
    assert rounds["next"]["series"] == "seed" and rounds["next"]["allowed"]
    assert rounds["next"]["typical_min_cents"] == 100_000_000
    api.post(f"{BASE}/finance/rounds", {"series": "a", "target_cents": 500_000_000}, 400)
    api.post(f"{BASE}/finance/rounds", {"series": "seed", "target_cents": 150_000_000}, 201)
    run_turn(path, loaded)
    (rnd,) = api.get(f"{BASE}/finance/rounds")["rounds"]
    assert rnd["status"] == "open" and rnd["term_sheets"]
    best = max(rnd["term_sheets"], key=lambda t: t["pre_money_cents"])
    preview = api.get(f"{BASE}/finance/term-sheets/{best['sheet_id']}/preview")
    assert preview["safe_conversion"] > 0 and preview["pool_top_up"] > 0
    assert preview["board_after"] == {"common": 1, "investor": 1, "independent": 0}
    # M4b: each open sheet says what the founder would own; the preview flags holders.
    (you,) = [line for line in preview["lines"] if line["is_founder"]]
    assert best["founder_fraction_after"] == pytest.approx(you["fraction_after"])
    assert [line["new"] for line in preview["lines"]][-2:] == [True, True]  # SAFE, the firm
    assert preview["founder_keeps_tie"] and preview["energy_cost"] == 5
    assert rnd["firms_asked"] == 4  # the seed firms in investors.yaml
    assert api.get(f"{BASE}/finance/safes")["blocked"] is not None  # a priced round is open
    api.post(f"{BASE}/finance/term-sheets/{best['sheet_id']}/accept")
    api.get(f"{BASE}/finance/term-sheets/999/preview", status=404)
    run_turn(path, loaded)

    after = api.get(f"{BASE}/finance/captable")
    assert after["fd_shares"] == preview["fd_after"]  # the preview matches the close
    shares = {h["holder"]: h["shares"] for h in after["holders"]}
    for line in preview["lines"]:
        assert shares[line["holder"]] == line["shares_after"], line["holder"]
    assert after["share_price_dollars"] == preview["share_price_dollars"]
    (closed,) = api.get(f"{BASE}/finance/rounds")["rounds"]
    assert closed["status"] == "closed" and closed["new_shares"] == preview["new_shares"]
    board = api.get(f"{BASE}/finance/board")
    assert [d["kind"] for d in board["directors"]] == ["common", "investor"]
    assert board["directors"][1]["firm"] == best["firm"]
    assert board["average_confidence"] is not None and board["label"] in {
        "confident",
        "watchful",
        "losing patience",
    }
    summary = api.get(f"{BASE}/finance/summary")
    assert summary["game_state"] == "active" and summary["runway_months"] is not None
    assert summary["stage"] == 0  # no hire yet: funding lifts stage 1, not 0 (14.8)
    assert summary["open_bridge_id"] is None

    # M4b: ownership over time, the board's trend inputs and the Overview's funding tile.
    history = after["ownership_history"]
    assert [e["event"] for e in history] == ["founded", "safe", "round"]
    assert history[0]["founder_fraction"] == 0.9 and history[1]["founder_fraction"] == 0.9
    assert history[2]["founder_fraction"] == pytest.approx(after["founder_fraction"])
    assert (
        after["last_round_label"] == "Seed"
        and after["post_money_cents"] == (best["post_money_cents"])
    )
    assert (after["vesting_months"], after["cliff_months"]) == (48, 12)
    assert board["seats_by_kind"] == {"common": 1, "investor": 1, "independent": 0}
    assert not board["removal_possible"] and board["expected_growth"] == 2.0
    # The seed closed in March: that month end moved confidence and held a meeting.
    assert board["last_meeting"]["date_label"] == "Mar 2010"
    assert board["next_meeting_label"] == "Jun 2010"
    assert len(board["directors"][1]["history"]) == 1
    run_turn(path, loaded)
    board = api.get(f"{BASE}/finance/board")
    assert len(board["directors"][1]["history"]) == 2 and board["trend"] is not None
    tile = api.get(f"{BASE}/overview")["funding"]
    assert tile["last_round_label"] == "Seed" and tile["board_label"] == board["label"]
    assert tile["founder_fraction"] == pytest.approx(after["founder_fraction"])


def test_game_over_refuses_turns_and_actions(setup: tuple[Client, Path]) -> None:
    api, path = setup
    with open_session(path) as session, session.begin():
        before = load_state(session)
        ended = replace(
            before, save_meta=replace(before.save_meta, game_state="bankrupt", ended_turn=0)
        )
        sync_state(session, before, ended)
    refused: Any = api.post(f"{BASE}/advance", status=409)
    assert refused["code"] == "game_over"
    body = {"amount_cents": 30_000_000, "cap_cents": 100_000_000}
    assert api.post(f"{BASE}/finance/safes", body, 409)["code"] == "game_over"
    api.post(f"{BASE}/recruitment/searches", {"role": "designer", "channel": "network"}, 409)
    overview = api.get(f"{BASE}/overview")  # reads still work
    assert (overview["game_state"], overview["ended_turn"]) == ("bankrupt", 0)
    assert api.get(f"{BASE}/finance/summary")["game_state"] == "bankrupt"
    api.get(f"{BASE}/finance/captable")
    api.get(f"{BASE}/finance/statements")
    over = api.get(f"{BASE}/finance/game-over")
    assert (over["game_state"], over["ended_label"], over["company_name"]) == (
        "bankrupt",
        "Jan 2010",
        "Fin Co",
    )
    assert over["founder_fraction"] == 0.9 and over["funding_summary"] is None
    assert over["directors"] == [] and over["months_lasted"] == 1


def test_stage_history_and_since(setup: tuple[Client, Path], loaded: LoadedData) -> None:
    api, _ = setup
    overview = api.get(f"{BASE}/overview")
    assert overview["stage_since_label"] == "Jan 2010"
    assert overview["stage_history"] == [
        {"stage": 0, "stage_label": overview["stage_label"], "turn": 0, "date_label": "Jan 2010"}
    ]
