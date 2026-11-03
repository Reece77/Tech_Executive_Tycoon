"""Create a save for the M11 Playwright flows (an e2e fixture tool). Never used by the game.

`lab <save dir> <name>`: a funded spinout ($20M) with six senior data scientists in an
"AI lab" team that works on no product.
`ahead <save dir> <name>`: the same, with a scripted AI lead of 35, past Deep learning's and
Transformers' thresholds at the first Continue (21.4).
`rival <save dir> <name>`: the same, with IBM 40 points ahead in devices, a domain whose
products come in M12b (so IBM is no direct competitor) (21.5).

Usage: uv run --project backend python tools/e2e_m11_save.py lab <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.balance.game import Game
from tst.balance.m8 import add_staff
from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, load_state, open_session, run_action
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.actions import CreateUnit, MovePerson
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.research.models import ResearchLead
from tst.sim.state import with_person_state

SEED = 29
FOUNDER = 1
IBM = 17
RESEARCHERS = 6
FUNDING_CENTS = 2_000_000_000  # $20M: the flows are not about solvency
AHEAD = 35.0  # AI lead: level 45 against Transformers' 43.5 once Deep learning's +5 is in
RIVAL_LEAD = 40.0


def lab(save_dir: Path, name: str, data: LoadedData, mode: str) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name="Kestrel", data=data, save_dir=save_dir
    )
    entry = LedgerEntry.transfer(
        turn=0,
        company_id=FOUNDER,
        memo="Fixture funding",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=FUNDING_CENTS,
    )
    with open_session(path) as session, session.begin():
        session.add(entry_to_row(entry))
        before = load_state(session)
        game = Game(data, before, {})
        people = add_staff(game, "data_scientist", "senior", RESEARCHERS)
        sync_state(session, before, game.state)
    run_action(path, data, CreateUnit(FOUNDER, "team", "AI lab"))
    for pid in people:
        run_action(path, data, MovePerson(FOUNDER, pid, 1))
    with open_session(path) as session, session.begin():
        before = load_state(session)
        leads = {
            "ahead": (ResearchLead(FOUNDER, "ai", AHEAD),),
            "rival": (ResearchLead(IBM, "devices", RIVAL_LEAD),),
        }.get(mode, ())
        state = replace(before, research_leads=leads)
        founder = state.person_state(FOUNDER)
        state = with_person_state(state, replace(founder, energy=60))  # a fresh month's energy
        sync_state(session, before, state)
    return path


def main(argv: list[str]) -> int:
    data = load_all(Settings().data_dir)
    if len(argv) == 3 and argv[0] in ("lab", "ahead", "rival"):
        print(lab(Path(argv[1]), argv[2], data, argv[0]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
