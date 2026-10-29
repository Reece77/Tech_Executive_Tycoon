"""Create a save where a rival has just approached one of the player's people (an e2e fixture
tool, M5). A funded spinout hires three engineers through the normal actions; then Zoho's
approach to the first of them is added as phase 2 would make it (formulas.md 15.6). It runs
before the API opens the file. Never used by the game itself.

Usage: uv run --project backend python tools/e2e_approach_save.py <save dir> <save name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.config import Settings
from tst.db.repository import create_save, load_state, open_session, run_action, run_turn
from tst.db.state_io import sync_state
from tst.loader import load_all
from tst.sim.actions import Interview, MakeOffer, OpenSearch
from tst.sim.rivals.decisions import approach
from tst.sim.state import with_approach

SEED = 16
FOUNDER = 1
HIRES = 3
RIVAL = "Zoho"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    save_dir, name = Path(argv[0]), argv[1]
    data = load_all(Settings().data_dir)
    path = create_save(
        name,
        SEED,
        "funded_spinout",
        company_name="Kestrel",
        data=data,
        save_dir=save_dir,
        mission=("ai", "enterprise"),
    )
    run_action(path, data, OpenSearch(FOUNDER, "software_engineer", "job_post"))
    run_turn(path, data)
    with open_session(path) as session:
        state = load_state(session)
    for candidate in state.candidates[:HIRES]:
        ask = state.person(candidate.person_id).salary_expectation_cents or 0
        run_action(path, data, Interview(FOUNDER, candidate.person_id))
        run_action(path, data, MakeOffer(FOUNDER, candidate.person_id, 2 * ask, 0))
    run_turn(path, data)
    with open_session(path) as session, session.begin():
        state = load_state(session)
        staff = sorted(e.person_id for e in state.staff(state.player.id) if e.person_id != FOUNDER)
        rival = next(c for c in state.companies if c.name == RIVAL)
        after = approach(state, rival, staff[0], data.balance, data.game_data)
        # Made in phase 2 of the month just played, so the next Continue answers it.
        made = replace(after.approaches[-1], made_turn=state.turn - 1)
        sync_state(session, state, with_approach(after, made))
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
