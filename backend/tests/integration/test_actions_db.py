"""Actions through the repository: one transaction each, logged with seq; replay."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import select

from tst.db.models import DecisionLogRow
from tst.db.repository import create_save, open_session, replay_save, run_action, run_turn
from tst.db.state_io import load_state
from tst.loader import LoadedData
from tst.sim.actions import CloseSearch, OpenSearch
from tst.sim.errors import InsufficientEnergyError


@pytest.fixture
def save(tmp_path: Path, loaded: LoadedData) -> Path:
    return create_save(
        "acts",
        11,
        "ex_big_tech_founders",
        company_name="Acts Co",
        data=loaded,
        save_dir=tmp_path / "saves",
        mission=("ai", "enterprise"),
    )


def test_actions_persist_and_log_seq(save: Path, loaded: LoadedData) -> None:
    run_action(save, loaded, OpenSearch(1, "software_engineer", "job_post"))
    run_action(save, loaded, OpenSearch(1, "designer", "network"))
    with open_session(save) as session:
        state = load_state(session)
        rows = session.scalars(select(DecisionLogRow).order_by(DecisionLogRow.id)).all()
    assert [s.role for s in state.searches] == ["software_engineer", "designer"]
    assert state.person_state(1).energy == 100 - 4 - 10
    assert [(r.kind, r.seq, r.turn) for r in rows] == [
        ("new_game", 0, 0),
        ("open_search", 1, 0),
        ("open_search", 2, 0),
    ]
    assert rows[0].payload["mission"] == ["ai", "enterprise"]


def test_failed_action_writes_nothing(save: Path, loaded: LoadedData) -> None:
    for _ in range(10):
        run_action(save, loaded, OpenSearch(1, "designer", "network"))
    before = _dump(save)
    with pytest.raises(InsufficientEnergyError):
        run_action(save, loaded, OpenSearch(1, "designer", "network"))
    assert _dump(save) == before


def _dump(path: Path) -> list[str]:
    conn = sqlite3.connect(path)
    try:
        return list(conn.iterdump())
    finally:
        conn.close()


def _tables(path: Path) -> dict[str, list[tuple[object, ...]]]:
    """Every table's rows, except the save's own name."""
    conn = sqlite3.connect(path)
    try:
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name != 'alembic_version'"
            )
        ]
        out = {}
        for name in sorted(names):
            rows = conn.execute(f"SELECT * FROM {name} ORDER BY 1").fetchall()
            if name == "save_meta":
                rows = [tuple(v for i, v in enumerate(r) if i != 1) for r in rows]  # drop name
            out[name] = rows
        return out
    finally:
        conn.close()


def test_replay_reproduces_the_save(save: Path, tmp_path: Path, loaded: LoadedData) -> None:
    run_action(save, loaded, OpenSearch(1, "software_engineer", "job_post"))
    run_turn(save, loaded)
    run_action(save, loaded, OpenSearch(1, "designer", "recruiter"))
    run_action(save, loaded, CloseSearch(1, 1))
    run_turn(save, loaded)
    run_turn(save, loaded)
    run_action(save, loaded, OpenSearch(1, "marketer", "network"))  # after the last Continue
    copy = replay_save(save, tmp_path / "replay", "acts-replay", loaded)
    assert _tables(copy) == _tables(save)
