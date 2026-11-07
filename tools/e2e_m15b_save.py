"""Create saves for the M15b Playwright flows (an e2e fixture tool). Never used by the game.

- `deadline <save dir> <name>`: the "Survive 2022" scenario (formulas.md 30.3) moved on to its
  deadline month, December 2023, with a profitable last eleven months: Continue plays the
  deadline's month end, which judges the goal a success and opens the result screen.
- `december <save dir> <name>`: a campaign played to December 2010, so Continue publishes
  January 2011's industry rankings (30.4).
- `pitch <save dir> <name>`: M13b's company with a CPO and a CTO with authority
  (tools/e2e_m13b_save.py), at a seed whose first month brings a pitch and no event, so
  Continue until (30.5) stops at the pitch.

Usage: uv run --project backend python tools/e2e_m15b_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.config import Settings
from tst.db.models import SaveMetaRow
from tst.db.repository import create_save, load_state, open_session, run_turn
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.modes.scenarios import scenario_spec
from tst.sim.state import with_company

PROFIT_CENTS = 400_000_00  # $400k a month operating profit, the eleven months before
REVENUE_CENTS = 900_000_00  # on $900k a month of revenue
MONTHS = 11


def deadline(save_dir: Path, name: str, data: LoadedData) -> Path:
    mode = scenario_spec("survive_2022", data.game_data)
    path = create_save(
        name,
        5,
        "funded_spinout",
        company_name="Ledgerly Inc",
        data=data,
        save_dir=save_dir,
        mode=mode,
    )
    h = data.game_data.historical_scenario("survive_2022")
    assert h is not None
    last = ym_to_turn(*h.deadline)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        company = before.player
        state = with_company(
            before,
            replace(
                company,
                op_history=(*company.op_history, *([PROFIT_CENTS] * MONTHS))[-MONTHS:],
                mrr_history=(*company.mrr_history, *([REVENUE_CENTS] * MONTHS))[-MONTHS:],
            ),
        )
        state = replace(state, turn=last)
        sync_state(session, before, state)
        meta = session.get(SaveMetaRow, 1)
        assert meta is not None
        meta.current_turn = last
    return path


def december(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = create_save(
        name, 3, "funded_spinout", company_name="Kestrel", data=data, save_dir=save_dir
    )
    for _ in range(11):  # January to November 2010
        run_turn(path, data)
    return path


def pitch(save_dir: Path, name: str, data: LoadedData) -> Path:
    import shutil

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from e2e_m13b_save import SEEDS, _company
    from tst.db.repository import continue_until

    for seed in SEEDS:
        path, _, _ = _company(save_dir, name, seed, data, ("cpo", "cto"))
        trial = path.with_name(f"{name}-trial.tst.sqlite")
        shutil.copyfile(path, trial)
        played, why = continue_until(trial, data)
        trial.unlink()
        if (played, why) == (1, "pitch"):
            return path
        path.unlink()
    raise SystemExit("no seed stops at a pitch in its first month")


def main(argv: list[str]) -> int:
    data = load_all(Settings().data_dir)
    modes = {"deadline": deadline, "december": december, "pitch": pitch}
    if len(argv) == 3 and argv[0] in modes:
        print(modes[argv[0]](Path(argv[1]), argv[2], data))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
