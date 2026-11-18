"""Profile a 2039 save's months (M30): time 12 months as the player plays them, then run 6
more under cProfile, and write the timings, a pstats file and two text tables (cumulative and
own time) to an output folder. A measuring tool, never part of the game: it plays a copy.

    uv run --project backend python tools/m30_profile.py <save.tst.sqlite> <out dir>
"""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import pstats
import shutil
import statistics
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

WARM_UP = 2
TIMED = 12
PROFILED = 6


def main() -> int:
    from tests.helpers import answer_critical, continue_at_end
    from tst.db import migrate
    from tst.db.repository import load_state, open_session, run_turn
    from tst.loader import load_all

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("save", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "copy" / args.save.name
    path.parent.mkdir(exist_ok=True)
    shutil.copy(args.save, path)
    migrate.ensure_current(path)
    data = load_all(BACKEND / "data")
    continue_at_end(path, data)  # M37 (52.1): a 2039 save plays on in dynasty mode
    with open_session(path) as session:
        state = load_state(session)
    turn, staff = state.turn, len(state.staff(state.player.id))
    for _ in range(WARM_UP):
        answer_critical(path, data)
        run_turn(path, data)
    months = []
    for _ in range(TIMED):
        answer_critical(path, data)
        start = time.perf_counter()
        run_turn(path, data)
        months.append(round((time.perf_counter() - start) * 1000))
    profile = cProfile.Profile()
    for _ in range(PROFILED):
        answer_critical(path, data)
        profile.enable()
        run_turn(path, data)
        profile.disable()
    profile.dump_stats(str(args.out / "months.pstats"))
    for key, name in (("cumulative", "cumulative.txt"), ("tottime", "own.txt")):
        text = io.StringIO()
        pstats.Stats(profile, stream=text).sort_stats(key).print_stats(120)
        (args.out / name).write_text(text.getvalue(), encoding="utf-8")
    report = {
        "from_turn": turn,
        "staff": staff,
        "months_ms": months,
        "median_ms": statistics.median(months),
        "max_ms": max(months),
        "profiled_months": PROFILED,
    }
    (args.out / "timings.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report))
    shutil.rmtree(path.parent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
