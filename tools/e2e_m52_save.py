"""Create saves for the M52 Playwright flows (an e2e fixture tool). Never used by the game.

- `end2069 <save dir> <name>`: a dynasty campaign whose December 2069 has been played, over
  (`dynasty_end`), so the game-over screen offers to continue in sandbox (flow c). The month is
  moved on directly (the world is January 2010's): the flow is about continuing, not the world.

Usage: uv run --project backend python tools/e2e_m52_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

from tst.config import Settings
from tst.db import repository
from tst.db.repository import create_save, load_state, open_session
from tst.db.state_io import read_meta, sync_state
from tst.loader import load_all
from tst.sim.dynasty.mode import close_at_final, final_turn

SEED: Final = 52


def end2069(save_dir: Path, name: str) -> Path:
    data = load_all(Settings().data_dir)
    path = create_save(
        name,
        SEED,
        "funded_spinout",
        company_name="Longview",
        data=data,
        save_dir=save_dir,
        length="dynasty",
    )
    with open_session(path) as session, session.begin():
        before = load_state(session)
        after = close_at_final(replace(before, turn=final_turn(data.balance)), data.balance)
        sync_state(session, before, after)
        meta = read_meta(session)
        meta.current_turn = after.turn
    repository._LAST.clear()
    return path


def main() -> None:
    mode, save_dir, name = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    if mode != "end2069":
        raise SystemExit(f"unknown mode {mode!r}")
    print(end2069(save_dir, name))


if __name__ == "__main__":
    main()
