"""M14b persistence (0033): press moments, promises, credibility, feuds, rival CEOs'
statements, departures, and the new search and plan fields survive a save and reload; the
live set matches `live_view`, the database keeps every row, and the press counters continue
from the largest stored id."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import func, select

from tests.helpers import play_turn
from tst.db.models import DepartureRow, PressMomentRow, StatementRow
from tst.db.repository import create_save, open_session
from tst.db.state_io import live_view, load_state, read_meta, sync_state
from tst.loader import LoadedData
from tst.sim.hiring.models import Search
from tst.sim.org.models import HiringPlan
from tst.sim.press.models import Credibility, Departure, Feud, PressMoment, Promise, Statement
from tst.sim.state import GameState

TURN = 50


def _objects(state: GameState) -> dict[str, tuple[object, ...]]:
    cid = state.player.id
    rival = next(c.id for c in state.companies if c.id != cid)
    person = state.employments[0].person_id
    moments = (
        PressMoment(1, cid, "launch", 20, "answered", 21, tone="bold", answered_turn=21),  # old
        PressMoment(2, cid, "breach", 10, "pending"),  # old but pending: live
        PressMoment(
            4,
            cid,
            "jab",
            45,
            "answered",
            event_turn=46,
            product_id=11,
            rival_id=rival,
            facts=(("rival", "Acme"), ("share_bp", 1_250), ("product", "Widget")),
            tone="measured",
            answered_turn=46,
            share_bp=1_250,
            backfired=True,
        ),
        PressMoment(6, cid, "earnings", 49, "queued", event_turn=51),
    )
    promises = (
        Promise(1, cid, "ship", 5, 12, status="kept", resolved_turn=11),  # old: still live
        Promise(
            3,
            cid,
            "no_price_rise",
            46,
            58,
            moment_id=4,
            product_id=11,
            prices=(("enterprise", 120_000), ("smb", 4_900)),
            ambition=0.375,
            audience=1.5,
            status="broken",
            resolved_turn=48,
            reminder_turn=50,
        ),
        Promise(
            5,
            cid,
            "research",
            47,
            60,
            domain="ai",
            level=3,
            baseline=1,
            ambition=0.123456789,
        ),
    )
    cred = (
        Credibility(
            cid,
            61.234567891,
            history=((48, -4.5, "broke a promise"), (49, 0.25, "drift")),
            fired_turn=49,
            fired=3,
            staff_start=20,
        ),
    )
    feuds = (Feud(cid, rival, 72.5, ((46, 12.0, "a jab answered boldly"),), rivalry_turn=46),)
    statements = (
        Statement(2, rival, 900, 10, "statement", "We are pleased."),  # older than 24 months
        Statement(5, rival, 900, 45, "jab", "They will never ship.", product_id=11),
        Statement(7, rival, 900, 49, "answer", "We welcome the competition."),
    )
    departures = (
        Departure(person, cid, "software_engineer", "senior", None, "poached", 40),  # old
        Departure(person + 1, cid, "designer", "mid", None, "resigned", 47),
        Departure(person + 2, cid, "sales_rep", "junior", None, "resigned", 49),
    )
    search = Search(
        id=state.next_ids.search,
        company_id=cid,
        role="software_engineer",
        channel="job_post",
        actor_id=person,
        opened_turn=TURN,
        interest="ai",
    )
    plan = HiringPlan(
        id=state.next_ids.plan,
        company_id=cid,
        owner_id=person,
        unit_id=None,
        role="software_engineer",
        target=1,
        channel="job_post",
        ratio_bp=10_000,
        equity_bp=0,
        created_turn=TURN,
        interest="ai",
        replace_of=person + 1,
        level="senior",
    )
    return {
        "press_moments": moments,
        "promises": promises,
        "credibility": cred,
        "feuds": feuds,
        "statements": statements,
        "departures": departures,
        "searches": (*state.searches, search),
        "plans": (*state.plans, plan),
    }


def _save(
    tmp_path: Path, loaded: LoadedData, name: str
) -> tuple[Path, dict[str, tuple[object, ...]]]:
    path = create_save(
        name, 4, "funded_spinout", company_name="Press Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        read_meta(session).current_turn = TURN
        session.flush()
        before = load_state(session)
        assert before.press_moments == () and before.promises == () and before.departures == ()
        assert (before.next_ids.press_moment, before.next_ids.promise) == (1, 1)
        assert before.next_ids.statement == 1
        objects = _objects(before)
        sync_state(session, before, replace(before, **objects))  # type: ignore[arg-type]
    return path, objects


def test_m14b_round_trip(tmp_path: Path, loaded: LoadedData) -> None:
    path, objects = _save(tmp_path, loaded, "press")
    with open_session(path) as session:
        state = load_state(session)
        counts = tuple(
            session.scalar(select(func.count()).select_from(m))
            for m in (PressMomentRow, StatementRow, DepartureRow)
        )
    assert counts == (4, 3, 3)  # the database keeps every row

    # The live set: pending and queued moments and those of the last 12 months; every promise;
    # statements of the last 24 months; departures of the last 3 months.
    assert state.press_moments == objects["press_moments"][1:]
    assert state.promises == objects["promises"]
    assert state.credibility == objects["credibility"]
    assert state.feuds == objects["feuds"]
    assert state.statements == objects["statements"][1:]
    assert state.departures == objects["departures"][1:]
    assert state.searches == objects["searches"]
    assert state.plans == objects["plans"]
    assert isinstance(state.press_moments[1].facts[0], tuple)
    assert state.press_moments[1].facts[1] == ("share_bp", 1_250)
    assert isinstance(state.promises[1].prices[0], tuple)
    assert isinstance(state.credibility[0].history[0], tuple)
    assert isinstance(state.feuds[0].causes[0], tuple)
    assert state.next_ids.press_moment == 7
    assert state.next_ids.promise == 6
    assert state.next_ids.statement == 8

    written = replace(state, **objects)  # type: ignore[arg-type]
    view = live_view(written)
    assert view.press_moments == state.press_moments
    assert view.statements == state.statements
    assert view.departures == state.departures
    assert live_view(state) == state


def test_m14b_changes_are_written(tmp_path: Path, loaded: LoadedData) -> None:
    path, _ = _save(tmp_path, loaded, "press2")
    with open_session(path) as session, session.begin():
        old = load_state(session)
        cred = replace(old.credibility[0], value=55.5, history=((TURN, -5.75, "a backfire"),))
        feud = replace(old.feuds[0], score=80.0)
        promise = replace(old.promises[2], status="kept", resolved_turn=TURN)
        plan = replace(old.plans[-1], interest=None, replace_of=None, level=None)
        new = replace(
            old,
            credibility=(cred,),
            feuds=(feud,),
            promises=(*old.promises[:2], promise),
            plans=(*old.plans[:-1], plan),
        )
        sync_state(session, old, new)
    with open_session(path) as session:
        state = load_state(session)
    assert state.credibility == (cred,)
    assert state.feuds == (feud,)
    assert state.promises[2] == promise
    assert state.plans[-1] == plan


def test_a_turn_keeps_the_cache_in_step(
    tmp_path: Path, loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TST_STATE_CACHE_CHECK", "1")
    path = create_save(
        "pcache", 4, "funded_spinout", company_name="Co", data=loaded, save_dir=tmp_path
    )
    for _ in range(2):
        play_turn(path, loaded)
