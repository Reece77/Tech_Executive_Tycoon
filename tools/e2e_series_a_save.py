"""Create a save that is ready for a Series A (an e2e fixture tool, M4c).

Playwright's nominee flow needs a Series A candidate; reaching $1M ARR through the screens
takes about fifteen scripted months. This builds the save through the normal repository
calls instead: a funded spinout (seed 16) opens a job post, hires up to four engineers at
twice their ask after interviewing them, and then has its revenue history set to a $2M ARR
(seven equal month ends, so six-month growth is zero). It runs before the API ever opens the
file. Never used by the game itself.

Usage: uv run --project backend python tools/e2e_series_a_save.py <save dir> <save name>
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

SEED = 16
FOUNDER = 1
HIRES = 4
ARR_CENTS = 200_000_000  # $2M
HISTORY = 7  # the current month end and the six before it (formulas.md 14.3)


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
        company_name="Series Co",
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
        company = replace(state.player, mrr_history=(ARR_CENTS // 12,) * HISTORY)
        companies = tuple(company if c.id == company.id else c for c in state.companies)
        sync_state(session, state, replace(state, companies=companies))
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
