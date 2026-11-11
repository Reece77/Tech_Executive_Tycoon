"""Print M23b's v3 balance targets (docs/tasks/M23b-v3-balance.md; tst.balance.v3). Exits 1 if a
target misses beyond a recorded known miss.

uv run --project backend python tools/v3_targets.py --integration  # I1-I3: 7 x 10 seeds x 240
uv run --project backend python tools/v3_targets.py --shocks       # S1, S2
uv run --project backend python tools/v3_targets.py --long         # F1, L1-L4: 3 x 10 seeds x 360
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    parser.add_argument("--integration", action="store_true", help="I1-I3, 20 years")
    parser.add_argument("--shocks", action="store_true", help="S1-S2")
    parser.add_argument("--long", action="store_true", help="F1 and L1-L4, 30 years")
    parser.add_argument("--runs", action="store_true", help="also print one line per run")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    if not (args.integration or args.shocks or args.long):
        args.integration = args.shocks = args.long = True

    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import v3
    from tst.balance.known_misses import verdict
    from tst.balance.report import table

    started = time.perf_counter()
    seeds = args.seeds or list(v3.SEEDS)
    rows = []
    if args.shocks:
        rows += v3.shock_rows(v3.lithium_rise(), [v3.gallium_run(s) for s in seeds])
    if args.integration:
        runs = v3.run_all(v3.COMPARED, seeds, v3.YEARS_20, jobs=args.jobs)
        if args.runs:
            print(v3.run_table(runs), end="\n\n")
            print(v3.rung_table([r for r in runs if r.rungs]), end="\n\n")
        rows += v3.integration_rows(runs)
    if args.long:
        runs = v3.run_all(v3.LONG_STRATEGIES, seeds, v3.LONG_TURNS, jobs=args.jobs)
        if args.runs:
            print(v3.run_table(runs), end="\n\n")
            print(v3.rung_table(runs), end="\n\n")
        rows += v3.fab_rows(runs) + v3.long_rows(runs)
    print(table(rows))
    print(f"\n{time.perf_counter() - started:.0f} s wall clock with {args.jobs} jobs")
    return 1 if any(verdict(r) == "fail" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
