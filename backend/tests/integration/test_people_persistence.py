"""People persistence (M1a): round trips, turn updates, and the 0001 -> 0002 upgrade."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from tst.db import migrate
from tst.db.models import (
    SCHEMA_VERSION,
    EmploymentRow,
    PersonRow,
    PersonStateRow,
    RelationshipRow,
)
from tst.db.repository import create_save, load_state, open_session, run_turn
from tst.db.session import make_engine
from tst.loader import LoadedData
from tst.sim.people.founder import FounderSpec
from tst.sim.setup import new_game


@pytest.fixture
def save(tmp_path: Path, loaded: LoadedData) -> Path:
    return create_save(
        "people",
        42,
        "garage_bootstrap",
        company_name="People Co",
        data=loaded,
        save_dir=tmp_path,
        founder=FounderSpec("academic", personality_preset="scientist"),
    )


def test_state_round_trips(save: Path, loaded: LoadedData) -> None:
    scenario = loaded.game_data.scenario("garage_bootstrap")
    assert scenario is not None
    expected, _ = new_game(
        save_name="people",
        master_seed=42,
        scenario=scenario,
        difficulty="standard",
        company_name="People Co",
        founder=FounderSpec("academic", personality_preset="scientist"),
        balance=loaded.balance,
        data=loaded.game_data,
    )
    with open_session(save) as session:
        state = load_state(session)
    assert state.people == expected.people
    assert state.employments == expected.employments
    assert state.reveals == expected.reveals


def test_turns_update_people_in_place(save: Path, loaded: LoadedData) -> None:
    with open_session(save) as session:
        before = load_state(session).people[0]
    result = run_turn(save, loaded)
    with open_session(save) as session:
        after = load_state(session)
        # The founder, plus the incumbents' key people from id 1,000,001 (M5).
        player_people = select(func.count()).select_from(PersonRow).where(PersonRow.id < 1_000_001)
        assert session.scalar(player_people) == 1
        player_jobs = (
            select(func.count()).select_from(EmploymentRow).where(EmploymentRow.company_id == 1)
        )
        assert session.scalar(player_jobs) == 1
        # M1b: the founder's energy lives in person_state.
        states = select(func.count()).select_from(PersonStateRow)
        assert session.scalar(states.where(PersonStateRow.person_id < 1_000_001)) == 1
        assert session.scalar(select(func.count()).select_from(RelationshipRow)) == 0
    assert after.people == result.new_state.people
    assert after.people[0].skills != before.skills
    assert after.people[0].potential_ability == before.potential_ability
    assert result.snapshot.for_company(1).headcount == 1


def test_upgrade_from_0001_keeps_m0_data(tmp_path: Path, loaded: LoadedData) -> None:
    """ADR-0004: a save made at the previous schema head upgrades cleanly after a backup."""
    path = tmp_path / "old.tst.sqlite"
    engine = make_engine(path)
    engine.dispose()
    migrate._run(path, "0001_initial")
    engine = make_engine(path)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO save_meta (id, name, master_seed, scenario_id, difficulty, "
                "created_turn, current_turn, data_hashes, schema_version) "
                "VALUES (1, 'old', 7, 'garage_bootstrap', 'standard', 0, 3, '{}', 1)"
            )
        )
        conn.execute(text("INSERT INTO company VALUES (1, 'Old Co', 1, 0, 0)"))
    engine.dispose()
    assert migrate.current_revision(path) == "0001_initial"

    backup = migrate.ensure_current(path)
    assert backup is not None and backup.name == "old.turn-003.pre-migration-0001_initial.sqlite"
    assert migrate.current_revision(path) == migrate.head_revision()
    with open_session(path) as session:
        state = load_state(session)
        meta_version = session.execute(text("SELECT schema_version FROM save_meta")).scalar()
    assert meta_version == SCHEMA_VERSION
    assert state.turn == 3
    assert state.player.name == "Old Co"
    assert [p for p in state.people if p.id < 1_000_001] == []  # rivals' key people only (M5)

    migrate.downgrade(path, "0001_initial")
    with open_session(path) as session:
        assert session.execute(text("SELECT schema_version FROM save_meta")).scalar() == 1
