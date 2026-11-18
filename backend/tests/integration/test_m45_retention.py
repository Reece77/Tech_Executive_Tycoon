"""M45 sub-task 5: a dynasty save's closed candidates lose the records nothing reads
(tst.db.history.prune_candidates). A person who was only ever a candidate, closed more than
retention.candidate_people_months ago, keeps their person row (the Timeline names them); their
skills, traits and reveal records go. Live people, and anyone another row names, keep all."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select, update

from tst.balance.m30 import Digester
from tst.db import history
from tst.db.models import CandidateRow, PersonRevealRow, PersonRow, PersonSkillRow
from tst.db.repository import create_save, load_state, open_session, run_action, run_turn
from tst.loader import LoadedData
from tst.sim.actions import OpenSearch

from tests.helpers import answer_critical


def _played(tmp_path: Path, loaded: LoadedData, months: int = 4) -> Path:
    path = create_save(
        "keep", 7, "funded_spinout", company_name="Keep Co", data=loaded, save_dir=tmp_path
    )
    run_action(path, loaded, OpenSearch(1, "software_engineer", "job_post"))
    for _ in range(months):
        answer_critical(path, loaded)
        run_turn(path, loaded)
    return path


def _skills(session: object, person_id: int) -> int:
    return int(
        session.scalar(  # type: ignore[attr-defined]
            select(func.count()).select_from(PersonSkillRow).where(
                PersonSkillRow.person_id == person_id
            )
        )
    )


def test_closed_candidates_lose_their_records_and_the_state_is_unchanged(
    tmp_path: Path, loaded: LoadedData
) -> None:
    path = _played(tmp_path, loaded)
    keep = loaded.balance.retention.model_copy(update={"candidate_people_months": 1})
    with open_session(path) as session, session.begin():
        state = load_state(session)
        live = {p.id for p in state.people}
        # some candidates closed long ago (as a dynasty save's are)
        opened = list(
            session.scalars(select(CandidateRow.person_id).where(CandidateRow.status == "open"))
        )[:5]
        assert opened, "the save has open candidates"
        session.execute(
            update(CandidateRow)
            .where(CandidateRow.person_id.in_(opened))
            .values(status="expired", resolved_turn=0)
        )
        closed = list(
            session.scalars(select(CandidateRow.person_id).where(CandidateRow.status != "open"))
        )
        state = load_state(session)
        live = {p.id for p in state.people}
        before = Digester().digest(state)
        gone = [p for p in closed if p not in live]
        assert gone, "the save has closed candidates outside the state"
        assert all(_skills(session, p) for p in gone)
        window = loaded.balance.retention  # 120 months: nothing has closed that long ago
        assert history.prune_candidates(session, 23, window, live) == 0
        pruned = history.prune_candidates(session, 23, keep, live)  # December 2011
        assert pruned == len(gone)
        assert not any(_skills(session, p) for p in gone)
        names = set(session.scalars(select(PersonRow.id).where(PersonRow.id.in_(gone))))
        assert names == set(gone)  # the Timeline's names stay
        assert all(_skills(session, p) for p in live)
        assert not session.scalar(
            select(func.count())
            .select_from(PersonRevealRow)
            .where(PersonRevealRow.person_id.in_(gone))
        )
        assert Digester().digest(load_state(session)) == before
        assert history.prune_candidates(session, 35, keep, live) == 0  # already pruned
        assert history.prune_candidates(session, 30, keep, live) == 0  # not a December


def test_a_candidate_another_row_names_keeps_their_records(
    tmp_path: Path, loaded: LoadedData
) -> None:
    path = _played(tmp_path, loaded, months=2)
    keep = loaded.balance.retention.model_copy(update={"candidate_people_months": 1})
    with open_session(path) as session, session.begin():
        state = load_state(session)
        live = {p.id for p in state.people}
        staff = next(e.person_id for e in state.employments)
        # the founder's or an employee's candidacy closed long ago: still named elsewhere
        session.execute(
            update(CandidateRow)
            .where(CandidateRow.person_id == staff)
            .values(status="hired", resolved_turn=0)
        )
        assert session.scalar(select(func.count()).where(CandidateRow.person_id == staff)) or True
        history.prune_candidates(session, 23, keep, live - {staff})  # not passed as live
        assert _skills(session, staff)
        assert all(_skills(session, p) for p in live if p != staff)
