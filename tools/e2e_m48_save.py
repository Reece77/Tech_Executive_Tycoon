"""Create saves for the M48 Playwright flows, the API tests and the practice save (an e2e fixture
tool). Never used by the game.

- `reported <save dir> <name>`: M13's listed Kestrel played through its first full quarter
  with guidance at the consensus, so the report is in: in the quarter's first month the board
  meeting and the earnings call are both due.
- `miss <save dir> <name>`: the same with the quarter's guidance set 25% above the consensus,
  so the report was a miss (an earnings call after a miss).
- `boardroom <save dir> <name>` (the practice save `pt-boardroom`): Kestrel listed in 2024,
  played to January 2024 by the engine, its last quarter's guidance set 25% above the
  consensus (a miss), and an activist circling: the share price has sat below the activist's
  bar for all but the last two of the months that bring one (25.4), so one arrives unless the
  price recovers (sentiment is set just under the bar).

Usage: uv run --project backend python tools/e2e_m48_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

import e2e_m13_save as m13
from tst.config import Settings
from tst.db.repository import run_action, run_turn
from tst.loader import LoadedData, load_all
from tst.sim.actions import SetGuidance
from tst.sim.calendar import ym_to_turn
from tst.sim.markets_public.public import consensus
from tst.sim.state import public_of, with_public

MISS: Final = 1.25  # guidance x the consensus: a miss
BOARDROOM_YEAR: Final = 2024
CIRCLING: Final = 2  # months short of the activist's trigger
SENTIMENT_GAP: Final = 0.04  # sentiment this far under the activist's bar (P / V_f per share)


def _quarter(path: Path, data: LoadedData, guidance_mult: float) -> None:
    """Guidance for the quarter starting now, then the quarter played: its report is in."""
    state = m13._state(path)
    assert state.turn % 3 == 0, state.turn
    rev, margin = consensus(state, 1)
    run_action(path, data, SetGuidance(m13.FOUNDER, round(rev * guidance_mult), margin))
    for _ in range(3):
        run_turn(path, data)
        m13.answer_open(path, data)


def reported(save_dir: Path, name: str, data: LoadedData, guidance_mult: float = 1.0) -> Path:
    path = m13.eligible(save_dir, name, data)
    m13.play_chain(path, data)
    _quarter(path, data, guidance_mult)
    return path


def boardroom(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = m13.eligible(save_dir, name, data)
    m13.play_chain(path, data)
    target = ym_to_turn(BOARDROOM_YEAR, 1) - 3
    while m13._state(path).turn < target:
        run_turn(path, data)
        m13.answer_open(path, data)
    _quarter(path, data, MISS)
    trigger = data.balance.public.activist_trigger

    def circling(state):  # type: ignore[no-untyped-def]
        public = public_of(state, 1)
        assert public is not None
        return with_public(
            state,
            replace(
                public,
                sentiment=trigger.value_share - SENTIMENT_GAP,
                below_value_months=max(0, trigger.months - CIRCLING),
            ),
        )

    m13._edit(path, circling)
    return path


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, save_dir, name = argv[0], Path(argv[1]), argv[2]
    data = load_all(Settings().data_dir)
    if mode == "reported":
        path = reported(save_dir, name, data)
    elif mode == "miss":
        path = reported(save_dir, name, data, MISS)
    elif mode == "boardroom":
        path = boardroom(save_dir, name, data)
    else:
        print(__doc__)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
