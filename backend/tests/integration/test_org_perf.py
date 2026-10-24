"""M2a acceptance: 120 turns with 25 staff, 4 units and 3 hiring plans average under 1 s."""

from __future__ import annotations

import time
from pathlib import Path

from tests.integration.test_api_org import seed_staff
from tst.db.repository import create_save, load_state, open_session, run_action, run_turn
from tst.loader import LoadedData
from tst.sim.actions import CreatePlan, CreateUnit, MovePerson, SetLeader

STAFF = 24  # employees; 25 with the founder
TURNS = 120


def test_org_turn_time_budget(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "orgperf", 3, "funded_spinout", company_name="Perf Co", data=loaded, save_dir=tmp_path
    )
    seed_staff(path, loaded, STAFF)
    founder = 1
    run_action(path, loaded, CreateUnit(founder, "department", "Engineering"))
    for name in ("Platform", "Product"):
        run_action(path, loaded, CreateUnit(founder, "team", name, parent_id=1))
    run_action(path, loaded, CreateUnit(founder, "team", "Sales"))
    people = list(range(2, 2 + STAFF))
    for i, pid in enumerate(people):
        run_action(path, loaded, MovePerson(founder, pid, 1 + i % 4))
    for unit in range(1, 5):
        run_action(path, loaded, SetLeader(founder, unit, people[unit - 1]))
    for owner, role in ((6, "software_engineer"), (7, "designer"), (8, "data_scientist")):
        run_action(path, loaded, CreatePlan(founder, owner, role, 4, "any", 11_000, 0, 2))
    with open_session(path) as session:
        state = load_state(session)
    assert len(state.staff(1)) == STAFF + 1 and len(state.units) == 4 and len(state.plans) == 3

    start = time.perf_counter()
    for _ in range(TURNS):
        run_turn(path, loaded)
    per_turn = (time.perf_counter() - start) / TURNS
    with open_session(path) as session:
        state = load_state(session)
    print(
        f"{TURNS} turns: {per_turn * 1000:.0f} ms per turn; staff {len(state.staff(1))}, "
        f"units {len(state.units)}, plans {len(state.plans)}, "
        f"open candidates {len(state.candidates)}"
    )
    assert per_turn < 1.0
