"""Replay with reorganizations, raises and delegates (ADR-0014, ADR-0015).

Player actions are re-applied; delegate actions are recomputed from the plans and must
match the logged rows.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import select

from tests.integration.test_actions_db import _tables
from tst.db.models import DecisionLogRow
from tst.db.repository import (
    create_save,
    load_state,
    open_session,
    replay_save,
    run_action,
    run_turn,
)
from tst.loader import LoadedData
from tst.sim.actions import (
    CreatePlan,
    CreateUnit,
    GiveRaise,
    Interview,
    MakeOffer,
    MovePerson,
    OpenSearch,
    Promote,
    SetLeader,
    SetPolicy,
)
from tst.sim.errors import ReplayMismatchError


def build(tmp_path: Path, loaded: LoadedData) -> Path:
    """Hire two people by hand, make one a team lead and a delegate, and let them hire."""
    path = create_save(
        "org", 21, "ex_big_tech_founders", company_name="Org Co", data=loaded, save_dir=tmp_path
    )
    run_action(path, loaded, OpenSearch(1, "recruiter", "network"))
    run_action(path, loaded, OpenSearch(1, "software_engineer", "network"))
    run_turn(path, loaded)
    with open_session(path) as session:
        state = load_state(session)
    for candidate in state.candidates[:3]:
        ask = state.person(candidate.person_id).salary_expectation_cents or 0
        run_action(path, loaded, Interview(1, candidate.person_id))
        run_action(path, loaded, MakeOffer(1, candidate.person_id, round(ask * 1.3), 0))
    run_turn(path, loaded)
    with open_session(path) as session:
        state = load_state(session)
    staff = [e.person_id for e in state.staff(1) if e.person_id != 1]
    assert len(staff) >= 2, "the 1.3x offers should be accepted"
    lead, other = staff[0], staff[1]
    run_action(path, loaded, CreateUnit(1, "team", "Platform"))
    run_action(path, loaded, MovePerson(1, lead, 1))
    run_action(path, loaded, MovePerson(1, other, 1))
    run_action(path, loaded, SetLeader(1, 1, lead))
    run_action(path, loaded, SetPolicy(1, 1, "remote"))
    run_action(path, loaded, GiveRaise(1, other, 12_000_000))
    run_action(path, loaded, Promote(1, other))
    run_action(path, loaded, CreatePlan(1, lead, "software_engineer", 2, "any", 11_500, 0, 1))
    for _ in range(4):
        run_turn(path, loaded)
    return path


def test_replay_reproduces_a_save_with_org_and_delegates(
    tmp_path: Path, loaded: LoadedData
) -> None:
    save = build(tmp_path / "a", loaded)
    with open_session(save) as session:
        delegated = session.scalars(
            select(DecisionLogRow).where(DecisionLogRow.source == "delegate")
        ).all()
        kinds = {row.kind for row in delegated}
        assert {"open_search", "interview", "make_offer"} <= kinds
        assert all(row.actor_id != 1 and row.seq is not None for row in delegated)
        state = load_state(session)
    assert state.units and state.plans[0].hired >= 1
    copy = replay_save(save, tmp_path / "replay", "org-replay", loaded)
    assert _tables(copy) == _tables(save)


def test_replay_detects_a_changed_delegate_log(tmp_path: Path, loaded: LoadedData) -> None:
    save = build(tmp_path / "a", loaded)
    conn = sqlite3.connect(save)
    try:
        conn.execute(
            "DELETE FROM decision_log WHERE id = "
            "(SELECT MIN(id) FROM decision_log WHERE source = 'delegate')"
        )
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(ReplayMismatchError):
        replay_save(save, tmp_path / "replay", "bad-replay", loaded)
