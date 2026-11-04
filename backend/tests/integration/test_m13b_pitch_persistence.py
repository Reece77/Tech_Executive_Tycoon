"""M13b (0032): pitches and the pitch policy are written and read back exactly, and the
cached state equals a full load after a turn that pitches."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from tests.helpers import play_turn
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.org.models import Pitch, PitchPolicy


def test_pitches_round_trip(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "pitches", 4, "funded_spinout", company_name="Co", data=loaded, save_dir=tmp_path
    )
    pitch = Pitch(
        id=1,
        company_id=1,
        seat="cpo",
        person_id=1,
        turn=0,
        kind="new_product",
        params=(("category", "fintech"), ("segment", "smb"), ("team", 3)),
        title="a new Fintech product for SMB",
        why="because",
        cost_cents=12_345,
        capex_cents=0,
        monthly_cents=1_000,
        hires=3,
        unit="cents_month",
        low=10,
        high=30,
        risk="some",
        status="approved",
        resolved_turn=0,
        target_id=7,
        baseline=0,
        outcome="hit",
        outcome_turn=24,
        measured=25,
    )
    policy = PitchPolicy(1, 5_000_000, True)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, replace(before, pitches=(pitch,), pitch_policies=(policy,)))
    with open_session(path) as session:
        state = load_state(session)
    assert state.pitches == (pitch,)
    assert state.pitch_policies == (policy,)
    assert state.next_ids.pitch == 2
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, replace(before, pitches=(replace(pitch, status="declined"),)))
    with open_session(path) as session:
        assert load_state(session).pitches[0].status == "declined"


def test_a_turn_keeps_the_cache_in_step(tmp_path: Path, loaded: LoadedData, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("TST_STATE_CACHE_CHECK", "1")
    path = create_save(
        "pcache", 4, "funded_spinout", company_name="Co", data=loaded, save_dir=tmp_path
    )
    play_turn(path, loaded)
    play_turn(path, loaded)
