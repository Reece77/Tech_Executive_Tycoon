"""Relationships persist (M6 sub-task 2, migration 0015_relationships): pairs are written and
read back, a pair whose person left is deleted, and an older save upgrades."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from sqlalchemy import inspect, select

from tests.helpers import make_person, with_employee
from tst.db import migrate
from tst.db.models import RelationshipRow
from tst.db.repository import create_save, load_state, open_session, run_turn
from tst.db.state_io import sync_state
from tst.loader import LoadedData
from tst.sim.state import with_employment


def test_pairs_round_trip_and_end(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "rel", 4, "ex_big_tech_founders", company_name="Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        state = load_state(session)
        new = state
        for pid in (2, 3):
            new = with_employee(loaded, new, make_person(loaded, pid), 9_000_000)
        new = replace(new, next_ids=replace(new.next_ids, person=4))
        sync_state(session, state, new)
    run_turn(path, loaded)
    with open_session(path) as session:
        state = load_state(session)
        rows = session.scalars(select(RelationshipRow)).all()
    assert {r.key for r in state.relationships} == {(1, 2), (1, 3), (2, 3)}
    assert len(rows) == 3 and all(r.value == r.start_value for r in rows)  # first month
    with open_session(path) as session, session.begin():
        state = load_state(session)
        leaving = next(e for e in state.staff(1) if e.person_id == 3)
        sync_state(
            session,
            state,
            with_employment(state, replace(leaving, status="ended", end_turn=state.turn)),
        )
    run_turn(path, loaded)
    with open_session(path) as session:
        keys = {(r.person_id, r.other_person_id) for r in session.scalars(select(RelationshipRow))}
    assert keys == {(1, 2)}


def test_upgrade_from_0014_rebuilds_the_table(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "relup", 4, "ex_big_tech_founders", company_name="Co", data=loaded, save_dir=tmp_path
    )
    migrate.downgrade(path, "0014_free_agents")
    assert migrate.ensure_current(path) is not None
    with open_session(path) as session:
        columns = {c["name"] for c in inspect(session.connection()).get_columns("relationship")}
    assert columns == {"person_id", "other_person_id", "value", "start_value", "since_turn"}
    run_turn(path, loaded)
