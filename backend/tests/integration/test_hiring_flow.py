"""M1b acceptance through the save file: hiring 10 people, replay, and the turn time budget."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from sqlalchemy import text

from tst.db.repository import create_save, open_session, replay_save, run_action, run_turn
from tst.db.state_io import load_state
from tst.loader import LoadedData
from tst.sim.actions import Interview, MakeOffer, OpenSearch
from tst.sim.errors import InsufficientEnergyError, OptionPoolError
from tst.sim.state import GameState


def state_of(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


def offer_everyone(path: Path, loaded: LoadedData, ratio: float, equity_bp: int) -> None:
    """Offer ratio x the ask to every open candidate without an offer, interviewing first
    (ADR-0016) while the founder has energy."""
    state = state_of(path)
    for c in state.candidates:
        if state.pending_offer_for(c.person_id) is not None:
            continue
        ask = state.person(c.person_id).salary_expectation_cents or 0
        try:
            if c.interviewed_turn is None:
                run_action(path, loaded, Interview(1, c.person_id))
            run_action(path, loaded, MakeOffer(1, c.person_id, round(ask * ratio), equity_bp))
        except (OptionPoolError, InsufficientEnergyError):
            return


def staff_count(path: Path) -> int:
    return len(state_of(path).staff(1)) - 1  # without the founder


def test_hire_ten_within_six_turns_using_all_three_channels(
    tmp_path: Path, loaded: LoadedData
) -> None:
    path = create_save(
        "ten",
        11,
        "ex_big_tech_founders",
        company_name="Ten Co",
        data=loaded,
        save_dir=tmp_path,
        mission=("ai", "enterprise"),
    )
    run_action(path, loaded, OpenSearch(1, "software_engineer", "network"))
    run_action(path, loaded, OpenSearch(1, "software_engineer", "job_post"))
    run_action(path, loaded, OpenSearch(1, "product_manager", "recruiter"))
    for _ in range(6):
        run_turn(path, loaded)  # offers resolve in phase 1, batches arrive in phase 12
        if staff_count(path) >= 10:
            break
        for c in state_of(path).candidates[:2]:
            run_action(path, loaded, Interview(1, c.person_id))
        offer_everyone(path, loaded, 1.2, 50)
    with open_session(path) as session:
        channels = {
            row[0]
            for row in session.execute(
                text("SELECT channel FROM candidate WHERE status = 'hired'")
            ).all()
        }
    state = state_of(path)
    print(f"hired {staff_count(path)} by turn {state.turn} via {sorted(channels)}")
    assert staff_count(path) >= 10
    assert state.turn <= 6
    assert channels == {"network", "job_post", "recruiter"}
    assert state.player.stage == 1


def _tables(path: Path) -> dict[str, list[tuple[object, ...]]]:
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
            rows = conn.execute(f"SELECT * FROM {name} ORDER BY 1, 2").fetchall()
            if name == "save_meta":
                rows = [tuple(v for i, v in enumerate(r) if i != 1) for r in rows]
            out[name] = rows
        return out
    finally:
        conn.close()


def test_replay_with_hiring_reproduces_the_save(tmp_path: Path, loaded: LoadedData) -> None:
    """Acceptance: start state + logged actions + turns reproduce the save exactly."""
    path = create_save(
        "orig", 5, "ex_big_tech_founders", company_name="Co", data=loaded, save_dir=tmp_path / "a"
    )
    run_action(path, loaded, OpenSearch(1, "designer", "job_post"))
    run_action(path, loaded, OpenSearch(1, "data_scientist", "recruiter"))
    for _ in range(4):
        run_turn(path, loaded)
        state = state_of(path)
        if state.candidates:
            run_action(path, loaded, Interview(1, state.candidates[0].person_id))
        offer_everyone(path, loaded, 1.05, 25)
    run_turn(path, loaded)
    assert staff_count(path) > 0
    copy = replay_save(path, tmp_path / "b", "copy", loaded)
    assert _tables(copy) == _tables(path)


def test_turn_time_budget(tmp_path: Path, loaded: LoadedData) -> None:
    """ADR-0006: 120 turns with 10 staff and an open job post average under 1 s per turn."""
    path = create_save(
        "perf", 3, "funded_spinout", company_name="Perf Co", data=loaded, save_dir=tmp_path
    )
    run_action(path, loaded, OpenSearch(1, "software_engineer", "job_post"))
    run_action(path, loaded, OpenSearch(1, "designer", "recruiter"))
    while staff_count(path) < 10 and state_of(path).turn < 12:
        run_turn(path, loaded)
        offer_everyone(path, loaded, 1.3, 0)
    run_turn(path, loaded)
    assert staff_count(path) >= 10
    start = time.perf_counter()
    turns = 120
    for _ in range(turns):
        run_turn(path, loaded)
    per_turn = (time.perf_counter() - start) / turns
    state = state_of(path)
    print(
        f"{turns} turns: {per_turn * 1000:.0f} ms per turn; staff {staff_count(path)}, "
        f"open candidates {len(state.candidates)}"
    )
    assert any(s.channel == "job_post" for s in state.searches)
    assert per_turn < 1.0
