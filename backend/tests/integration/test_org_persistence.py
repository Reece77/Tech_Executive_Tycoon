"""M2a state and persistence: units, plans, raises, interview record, decision source."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from sqlalchemy import select, text

from tests.helpers import make_person, with_candidates, with_employee
from tst.db import migrate
from tst.db.models import SCHEMA_VERSION, DecisionLogRow, HiringPlanRow, OrgUnitRow
from tst.db.repository import create_save, open_session, run_action
from tst.db.session import make_engine
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.actions import Interview, OpenSearch
from tst.sim.org.models import HiringPlan, OrgUnit, PlanActivity
from tst.sim.state import with_company, with_employment, with_plan, with_unit


def test_org_state_round_trips(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "org", 3, "ex_big_tech_founders", company_name="Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        before = load_state(session)
        assert before.units == () and before.plans == ()
        assert before.player.work_policy == "office"
        state = with_employee(loaded, before, make_person(loaded, 2), 9_000_000)
        state = with_candidates(loaded, state, 2)
        unit_id, ids = state.next_ids.take("unit")
        plan_id, ids = ids.take("plan")
        state = replace(state, next_ids=ids)
        state = with_unit(
            state,
            OrgUnit(unit_id, 1, "team", "Platform", None, 2, "remote", created_turn=0),
        )
        employment = state.employment_of(2)
        assert employment is not None
        state = with_employment(state, replace(employment, unit_id=unit_id, last_raise_turn=0))
        state = with_plan(
            state,
            HiringPlan(
                plan_id,
                1,
                owner_id=2,
                unit_id=unit_id,
                role="software_engineer",
                target=3,
                channel="any",
                ratio_bp=11000,
                equity_bp=10,
                created_turn=0,
                last_activity=PlanActivity(turn=0, interviews=2, offers=1),
            ),
        )
        candidate = state.candidates[0]
        state = replace(state, candidates=(replace(candidate, interviewed_turn=0),))
        state = with_company(state, replace(state.player, work_policy="remote"))
        sync_state(session, before, state)
    with open_session(path) as session:
        loaded_state = load_state(session)
    assert loaded_state.units == state.units
    assert loaded_state.plans == state.plans
    assert loaded_state.employments == state.employments
    assert loaded_state.candidates[0].interviewed_turn == 0
    assert loaded_state.player.work_policy == "remote"
    assert loaded_state.next_ids == state.next_ids


def test_closed_and_dissolved_records_leave_the_live_state(
    tmp_path: Path, loaded: LoadedData
) -> None:
    path = create_save(
        "live", 3, "ex_big_tech_founders", company_name="Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        before = load_state(session)
        state = with_employee(loaded, before, make_person(loaded, 2), 9_000_000)
        state = with_unit(
            state,
            OrgUnit(1, 1, "team", "Gone", None, None, None, 0, "dissolved", dissolved_turn=0),
        )
        state = with_plan(
            state,
            HiringPlan(1, 1, 2, None, "designer", 1, "network", 10000, 0, 0, "closed"),
        )
        sync_state(session, before, state)
    with open_session(path) as session:
        assert load_state(session).units == () and load_state(session).plans == ()
        assert session.scalar(select(OrgUnitRow.status)) == "dissolved"
        assert session.scalar(select(HiringPlanRow.status)) == "closed"


def test_player_actions_log_source_and_actor(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "src", 3, "ex_big_tech_founders", company_name="Co", data=loaded, save_dir=tmp_path
    )
    run_action(path, loaded, OpenSearch(1, "software_engineer", "network"))
    with open_session(path) as session:
        row = session.scalars(select(DecisionLogRow).where(DecisionLogRow.seq == 1)).one()
    assert (row.source, row.actor_id, row.kind) == ("player", 1, "open_search")


def test_upgrade_from_0004_backfills_interviews_and_keeps_everyone_in_the_root(
    tmp_path: Path, loaded: LoadedData
) -> None:
    path = create_save(
        "old", 3, "ex_big_tech_founders", company_name="Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        before = load_state(session)
        state = with_candidates(loaded, with_employee(loaded, before, make_person(loaded, 2), 1), 2)
        sync_state(session, before, state)
    interviewed = state.candidates[0].person_id
    run_action(path, loaded, Interview(1, interviewed))
    migrate.downgrade(path, "0004_inbox")

    assert migrate.ensure_current(path) is not None
    with open_session(path) as session:
        state = load_state(session)
        logged = session.scalars(select(DecisionLogRow).where(DecisionLogRow.seq == 1)).one()
    assert {c.person_id: c.interviewed_turn for c in state.candidates} == {
        interviewed: 0,
        interviewed + 1: None,
    }
    assert all(e.unit_id is None for e in state.employments)
    assert state.units == () and state.plans == ()
    assert (state.next_ids.unit, state.next_ids.plan) == (1, 1)
    assert (logged.source, logged.actor_id) == ("player", 1)
    engine = make_engine(path)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT schema_version FROM save_meta")).scalar()
    engine.dispose()
    assert version == SCHEMA_VERSION
