"""Holiday (docs/formulas.md 17.1; M7b): N months equal N Continues, each stop reason, the
summary item, the CLI, and the API job (busy saves, Stop, refusals)."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from tests.helpers import fresh_game
from tests.integration.test_api_hiring import BASE, hiring_client
from tst import holiday
from tst.cli import app as cli_app
from tst.db import repository
from tst.db.models import InboxItemRow, LedgerLineRow, TurnSnapshotRow
from tst.loader import LoadedData
from tst.sim.events.models import EventRequest
from tst.sim.log import inbox_item

SEED = 42


def _new(loaded: LoadedData, save_dir: Path, name: str) -> Path:
    return repository.create_save(
        name, SEED, "garage_bootstrap", company_name="Kestrel", data=loaded, save_dir=save_dir
    )


def _rows(path: Path) -> dict[str, Any]:
    """Everything a Continue writes, for comparing two saves."""
    with repository.open_session(path) as session:
        state = repository.load_state(session)
        ledger = sorted(
            (line.account_code, line.amount_cents)
            for line in session.scalars(select(LedgerLineRow))
        )
        snaps = [
            (r.turn, r.company_id, r.kpis)
            for r in session.scalars(select(TurnSnapshotRow).order_by(TurnSnapshotRow.id))
        ]
        inbox = [
            (r.turn, r.template, r.title, r.body)
            for r in session.scalars(select(InboxItemRow).order_by(InboxItemRow.id))
            if r.template != holiday.SUMMARY_TEMPLATE
        ]
    return {"state": state, "ledger": ledger, "snapshots": snaps, "inbox": inbox}


def test_a_12_month_holiday_equals_12_continues(loaded: LoadedData, tmp_path: Path) -> None:
    away = _new(loaded, tmp_path, "away")
    home = _new(loaded, tmp_path, "home")
    result = holiday.run_holiday(away, loaded, 12, "critical")
    assert result.months_played == 12 and result.reason == "months"
    for _ in range(12):
        repository.run_turn(home, loaded)
    a, b = _rows(away), _rows(home)
    # M24 (32.1): a month on Holiday lowers the founder's stress; nothing else differs.
    (rested,), (worked,) = a["state"].founder_lives, b["state"].founder_lives
    assert rested.holiday_months == 12 and worked.holiday_months == 0
    assert rested.stress <= worked.stress
    assert any(why == "a month away" for _, _, why in rested.causes)
    assert not any(why == "a month away" for _, _, why in worked.causes)
    same = replace(
        a["state"], save_meta=b["state"].save_meta, founder_lives=b["state"].founder_lives
    )
    assert same == b["state"]
    assert a["ledger"] == b["ledger"] and a["snapshots"] == b["snapshots"]
    assert a["inbox"] == b["inbox"]


def test_the_summary_item_says_while_you_were_away(loaded: LoadedData, tmp_path: Path) -> None:
    path = _new(loaded, tmp_path, "sum")
    result = holiday.run_holiday(path, loaded, 3, "critical")
    with repository.open_session(path) as session:
        item = session.get(InboxItemRow, result.summary_item_id)
        assert item is not None
        assert item.template == "holiday_summary" and item.link_kind == "history"
        assert item.title.startswith("While you were away")
        for words in ("Cash:", "ARR:", "Staff:", "Average morale:", "the months you chose"):
            assert words in item.body
        assert "Events decided for you" in item.body  # the founder's early-days events


def test_stop_finishes_the_month_and_rolls_nothing_back(loaded: LoadedData, tmp_path: Path) -> None:
    path = _new(loaded, tmp_path, "stop")
    pressed = {"after": 2}
    played: list[int] = []
    result = holiday.run_holiday(
        path,
        loaded,
        12,
        "critical",
        should_stop=lambda: len(played) >= pressed["after"],
        on_month=lambda done, _turn: played.append(done),
    )
    assert result.reason == "stopped" and result.months_played == 2
    assert result.end.turn == 2  # both months committed


def test_an_event_at_the_stop_level_stops_it(loaded: LoadedData, tmp_path: Path) -> None:
    path = _new(loaded, tmp_path, "ev")
    result = holiday.run_holiday(path, loaded, 12, "minor")  # any event stops it
    assert result.reason == "event" and result.months_played < 12


# --- Each stop reason, in the order of 17.1 ------------------------------------------------


def _result(state: Any, *, requests: tuple[Any, ...] = (), logs: tuple[Any, ...] = ()) -> Any:
    """The parts of a TurnResult the stop rules read."""
    return SimpleNamespace(new_state=state, event_requests=requests, log_items=logs)


def _vitals(runway: int | None) -> holiday.Vitals:
    return holiday.Vitals(1, 100, 0, 1, None, runway)


def _request(state: Any, severity: str) -> EventRequest:
    return EventRequest(1, state.player.id, 1, "t", severity, "grounded", ())  # type: ignore[arg-type]


def _reason(result: Any, runway: int | None = 24, **kw: Any) -> holiday.StopReason | None:
    args: dict[str, Any] = {
        "stop": "major",
        "limit": 6,
        "warned": False,
        "done": 1,
        "months": 6,
        "pressed": False,
    } | kw
    return holiday._reason(
        result,
        _vitals(runway),
        args["stop"],
        args["limit"],
        args["warned"],
        args["done"],
        args["months"],
        args["pressed"],
    )


def test_each_stop_reason(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    quiet = _result(state)
    assert _reason(quiet) is None
    over = replace(state, save_meta=replace(state.save_meta, game_state="bankrupt"))
    assert _reason(_result(over), runway=1, done=6, pressed=True) == "game_over"
    # 2: an event at or above the stop level; a critical event always stops.
    assert _reason(_result(state, requests=(_request(state, "minor"),))) is None
    assert _reason(_result(state, requests=(_request(state, "major"),))) == "event"
    assert _reason(_result(state, requests=(_request(state, "minor"),)), stop="minor") == "event"
    critical = _result(state, requests=(_request(state, "critical"),))
    assert _reason(critical, stop="critical") == "event"
    # 3: runway below the limit for the first time, or below 3 months.
    assert _reason(quiet, runway=5) == "runway"
    assert _reason(quiet, runway=5, warned=True) is None
    assert _reason(quiet, runway=2, warned=True) == "runway"
    assert _reason(quiet, runway=None) is None  # not burning
    # 4: a term sheet, SAFE or bridge offer arrived.
    for template in ("term_sheets_arrived", "safe_filled", "bridge_offered"):
        logs = (inbox_item(1, state.player.id, template),)
        assert _reason(_result(state, logs=logs)) == "offer"
    rival = (inbox_item(1, state.player.id + 1000, "term_sheets_arrived"),)
    assert _reason(_result(state, logs=rival)) is None
    # 5 and 6.
    assert _reason(quiet, done=6, pressed=True) == "months"
    assert _reason(quiet, pressed=True) == "stopped"


def test_it_cannot_start_over_a_critical_event_or_after_the_end(
    loaded: LoadedData, tmp_path: Path
) -> None:
    path = _new(loaded, tmp_path, "nope")
    with pytest.raises(holiday.HolidayError):
        holiday.check_start(path, loaded, 0, "major")
    with pytest.raises(holiday.HolidayError):
        holiday.check_start(path, loaded, loaded.balance.holiday.max_months + 1, "major")
    with pytest.raises(holiday.HolidayError):
        holiday.check_start(path, loaded, 3, "sometimes")


# --- CLI and API ----------------------------------------------------------------------------


def test_cli_holiday(loaded: LoadedData, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TST_SAVE_DIR", str(tmp_path))
    _new(loaded, tmp_path, "cli")
    out = CliRunner().invoke(
        cli_app, ["holiday", "--save", "cli", "--months", "2", "--stop", "critical"]
    )
    assert out.exit_code == 0, out.output
    assert "Holiday: 2 month(s), now Mar 2010" in out.output
    assert "Cash:" in out.output
    bad = CliRunner().invoke(cli_app, ["holiday", "--save", "cli", "--stop", "never"])
    assert bad.exit_code == 1


def _wait(api: Any) -> Any:
    for _ in range(600):
        body = api.get(f"{BASE}/holiday")
        if body["status"] != "running":
            return body
        time.sleep(0.05)
    raise AssertionError("holiday did not finish")


def test_api_holiday_job(tmp_path: Path) -> None:
    with hiring_client(tmp_path) as api:
        idle = api.get(f"{BASE}/holiday")
        assert idle["status"] == "idle" and idle["default_months"] == 6
        assert idle["default_stop"] == "major" and idle["max_months"] == 24
        api.post(f"{BASE}/holiday", {"months": 99}, status=400)
        started = api.post(f"{BASE}/holiday", {"months": 2, "stop": "critical"}, status=202)
        assert started["status"] == "running" and started["months"] == 2
        done = _wait(api)
        assert done["status"] == "finished", done
        assert done["months_done"] >= 1 and done["summary_item_id"] is not None
        assert done["reason"] in ("months", "event", "runway", "offer")
        item = api.get(f"{BASE}/inbox?limit=50")
        assert any(m["item_id"] == done["summary_item_id"] for m in item["items"])


def test_api_a_running_holiday_makes_the_save_busy(loaded: LoadedData, tmp_path: Path) -> None:
    with hiring_client(tmp_path) as api:
        path = repository.save_path(tmp_path / "saves", "m1b")
        token = repository.reserve(path)  # a holiday in progress
        try:
            assert api.post(f"{BASE}/advance", status=409)["code"] == "save_busy"
            api.post(f"{BASE}/inbox/read-all", status=409)
            api.post(f"{BASE}/holiday", {"months": 2}, status=409)
            assert api.get(f"{BASE}/overview")["turn"] == 0  # reads still work
            with repository.holding(token):
                repository.run_turn(path, loaded)  # the job itself may write
        finally:
            repository.release(path, token)
        api.post(f"{BASE}/advance")
        assert api.post(f"{BASE}/holiday/stop")["status"] == "idle"
