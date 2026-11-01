"""Create saves for the M10 Playwright flows (an e2e fixture tool). Never used by the game.

- `spinout <save dir> <name>`: a new funded spinout. Its seed closed at game start, so
  venture debt is on offer at once (formulas.md 20.3).
- `breach <save dir> <name>`: a funded spinout that took $400,000 of venture debt, then a
  month whose burn the covenant cannot cover (the burn history is scripted), so the critical
  lender event is waiting when the save opens.
- `year <save dir> <name> <year>`: a new funded spinout whose calendar is set to December of
  <year> without playing the months between (the macro strip reads history for them).

Usage: uv run --project backend python tools/e2e_m10_save.py <mode> <save dir> <name> [year]
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.config import Settings
from tst.db.repository import create_save, load_state, open_session, run_action, run_turn
from tst.db.state_io import read_meta, sync_state
from tst.loader import LoadedData, load_all
from tst.sim.actions import TakeLoan
from tst.sim.calendar import ym_to_turn
from tst.sim.state import with_company

SEED = 5
FOUNDER = 1
LOAN_CENTS = 40_000_000  # $400,000
HUGE_BURN = 10**12  # cents: no cash covers three months of it


def _create(save_dir: Path, name: str, data: LoadedData) -> Path:
    return create_save(
        name,
        SEED,
        "funded_spinout",
        company_name="Debt Co",
        data=data,
        save_dir=save_dir,
        mission=("ai", "enterprise"),
    )


def breach(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _create(save_dir, name, data)
    run_action(path, data, TakeLoan(FOUNDER, "venture_debt", LOAN_CENTS))
    with open_session(path) as session, session.begin():
        before = load_state(session)
        company = replace(before.player, burn_history=(HUGE_BURN,))
        sync_state(session, before, with_company(before, company))
    run_turn(path, data)
    return path


def year(save_dir: Path, name: str, when: int, data: LoadedData) -> Path:
    path = _create(save_dir, name, data)
    with open_session(path) as session, session.begin():
        read_meta(session).current_turn = ym_to_turn(when, 12)
    return path


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, save_dir, name = argv[0], Path(argv[1]), argv[2]
    data = load_all(Settings().data_dir)
    if mode == "spinout":
        path = _create(save_dir, name, data)
    elif mode == "breach":
        path = breach(save_dir, name, data)
    elif mode == "year":
        path = year(save_dir, name, int(argv[3]), data)
    else:
        print(__doc__)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
