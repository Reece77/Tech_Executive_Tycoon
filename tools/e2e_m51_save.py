"""Move a scenario save for the M51 Playwright flows (an e2e fixture tool). Never used by the
game.

- `deadline <save dir> <name>`: an existing scenario save (started from the new-game screen)
  moved on to its deadline month without playing the months between, so Continue plays the
  deadline's month end, which judges the goal (formulas.md 63.1) and opens the result screen.

Usage: uv run --project backend python tools/e2e_m51_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.config import Settings
from tst.db.models import SaveMetaRow
from tst.db.repository import existing_save_path, load_state, open_session
from tst.db.state_io import sync_state
from tst.loader import load_all
from tst.sim.modes import scenarios as sc


def deadline(save_dir: Path, name: str) -> Path:
    data = load_all(Settings().data_dir)
    path = existing_save_path(save_dir, name)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        assert before.mode is not None and before.mode.scenario is not None
        last = sc.deadline_turn(sc.scenario(data.game_data, before.mode.scenario))
        sync_state(session, before, replace(before, turn=last))
        meta = session.get(SaveMetaRow, 1)
        assert meta is not None
        meta.current_turn = last
    return path


def main() -> None:
    mode, save_dir, name = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    if mode != "deadline":
        raise SystemExit(f"unknown mode {mode!r}")
    print(deadline(save_dir, name))


if __name__ == "__main__":
    main()
