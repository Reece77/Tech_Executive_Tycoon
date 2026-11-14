"""Create the M27a practice save (formulas.md 40; an e2e fixture tool). Never used by the game.

- `auto <save dir> <name>` (Reece's `pt-auto`): a stage-3 company with a live B2B SaaS
  product, every executive seat filled (CTO, CPO, CRO, CMO, COO, CFO), a few senior area leads
  (a recruiter, a research scientist, a site reliability engineer, a communications manager)
  and nothing automated yet: Automate everything has something to hand out.
- `cfo <save dir> <name>`: M10c's garage start at stage 3 with a senior finance manager
  appointed CFO and cash for about three months: given Treasury, the CFO proposes the seed
  (a one-off), which stops a holiday.

Usage: uv run --project backend python tools/e2e_m27a_save.py auto <save dir> <name>
"""

from __future__ import annotations

import sys
from pathlib import Path

from e2e_m10c_save import cfo, cro
from tst.balance.fixtures import finish
from tst.config import Settings
from tst.db.repository import load_state, open_session, run_action
from tst.loader import LoadedData, load_all
from tst.sim.actions import AppointExecutive

FOUNDER = 1
LEADS = (
    ("operations_manager", 1, "Operations"),
    ("marketing_manager", 1, "Sales"),
    ("recruiter", 1, "Operations"),
    ("research_scientist", 1, "Engineering"),
    ("site_reliability_engineer", 1, "Engineering"),
    ("communications_manager", 1, "Sales"),
)
SEATS = (("cpo", "product_manager"), ("cmo", "marketing_manager"), ("coo", "operations_manager"))
SEATS += (("cfo", "finance_manager"),)


def auto(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = cro(save_dir, name, data)  # stage 3, a live product, a CRO
    finish(path, data, team=True, specialists=LEADS)  # the core team and a CTO
    with open_session(path) as session:
        state = load_state(session)
    seated = {s.person_id for s in state.exec_seats if s.person_id is not None}
    for seat, role in SEATS:
        pick = next(
            e.person_id
            for e in state.staff(FOUNDER)
            if e.role == role
            and e.level in ("senior", "staff", "principal", "exec")
            and e.person_id not in seated
        )
        seated.add(pick)
        run_action(path, data, AppointExecutive(FOUNDER, seat, pick))
    return path


def main(argv: list[str]) -> int:
    data = load_all(Settings().data_dir)
    if len(argv) == 3 and argv[0] in ("auto", "cfo"):
        make = auto if argv[0] == "auto" else cfo
        print(make(Path(argv[1]), argv[2], data))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
