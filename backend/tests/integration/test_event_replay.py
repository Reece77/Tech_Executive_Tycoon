"""Replay reproduces a save with events, choices and a storyline without calling any adapter
(M6 acceptance, ADR-0005: events are stored, so replay copies them)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from tests.golden.test_golden import ledger_rows, snapshots
from tests.helpers import answer_critical
from tst.db import events as event_store
from tst.db.models import EventRow, StorylineRow
from tst.db.repository import (
    create_save,
    load_state,
    open_session,
    replay_save,
    run_action,
    run_turn,
)
from tst.loader import LoadedData
from tst.sim.actions import ChooseEvent, Interview, MakeOffer, OpenSearch

TURNS = 30


def _build(save_dir: Path, loaded: LoadedData) -> Path:
    path = create_save(
        "evrep", 6, "funded_spinout", company_name="Rep Co", data=loaded, save_dir=save_dir
    )
    run_action(path, loaded, OpenSearch(1, "software_engineer", "job_post"))
    for turn in range(TURNS):
        with open_session(path) as session:
            state = load_state(session)
        if turn == 1:
            for c in [c for c in state.open_candidates(1)][:3]:
                if (state.person_state(1).energy or 0) < 8:
                    break
                ask = state.person(c.person_id).salary_expectation_cents or 0
                run_action(path, loaded, Interview(1, c.person_id))
                run_action(path, loaded, MakeOffer(1, c.person_id, ask * 2, 0))
                with open_session(path) as session:
                    state = load_state(session)
        for event in state.open_events(1):  # answer every other event with its last choice
            if event.status == "open" and event.id % 2 == 0:
                run_action(path, loaded, ChooseEvent(1, event.id, event.choices[-1].key))
        answer_critical(path, loaded)
        run_turn(path, loaded)
    return path


def test_replay_copies_events_and_calls_no_adapter(
    tmp_path: Path, loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = _build(tmp_path / "a", loaded)
    with open_session(original) as session:
        events = session.scalars(select(EventRow)).all()
        stories = session.scalars(select(StorylineRow)).all()
        assert events and any(e.status == "answered" for e in events)
        assert stories, "the script should open a storyline"

    def no_adapter(_save_dir: Path) -> object:
        raise AssertionError("replay must not call an adapter")

    monkeypatch.setattr(event_store, "default_adapter", no_adapter)
    copy = replay_save(original, tmp_path / "b", "evrep-copy", loaded)
    assert snapshots(copy, None) == snapshots(original, None)
    assert [r[1:] for r in ledger_rows(copy)] == [r[1:] for r in ledger_rows(original)]

    def rows(path: Path) -> list[tuple[object, ...]]:
        with open_session(path) as session:
            return [
                (e.id, e.turn, e.template_id, e.status, e.title, e.choices, e.chosen)
                for e in session.scalars(select(EventRow).order_by(EventRow.id))
            ]

    assert rows(copy) == rows(original)
