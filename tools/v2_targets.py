"""Print docs/formulas.md 30.7's v2 balance targets (M15a). Exits 1 if a target misses.

uv run --project backend python tools/v2_targets.py              # V1-V4: 9 x 10 seeds x 120
uv run --project backend python tools/v2_targets.py --seeds-30   # V1 over 30 seeds
uv run --project backend python tools/v2_targets.py --long       # V5: 2 x 10 seeds to 2039
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
    parser.add_argument("--seeds-30", action="store_true", help="V1's 30-seed clause")
    parser.add_argument("--long", action="store_true", help="V5's 30-year runs")
    parser.add_argument("--runs", action="store_true", help="also print one line per run")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()

    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import v2
    from tst.balance.known_misses import verdict
    from tst.balance.report import _loaded, run_all, runs_table, table
    from tst.balance.strategies_v2 import STRATEGIES

    started = time.perf_counter()
    if args.long:
        seeds = args.seeds or list(v2.LONG_SEEDS)
        runs = v2.run_long(seeds, jobs=args.jobs)
        if args.runs:
            print(v2.long_table(runs), end="\n\n")
        data = _loaded("data").game_data
        open_ = [  # categories rival startups may be founded in (15.4); the rest are scheduled
            c.key
            for c in data.categories
            if not (c.capacity_market or c.sells_units or c.assembly_market)
        ]
        scheduled = [c.key for c in data.categories if c.key not in open_]
        rows = v2.long_rows(runs, open_, scheduled)
    else:
        seeds = args.seeds or list(v2.SEEDS_30 if args.seeds_30 else v2.SEEDS)
        results = run_all(
            seeds=seeds, strategies=list(STRATEGIES), difficulty_runs=False, jobs=args.jobs
        )
        if args.runs:
            print(runs_table(results), end="\n\n")
        rows = [v2.winners_row_30(results)] if args.seeds_30 else v2.ten_year_rows(results)
    print(table(rows))
    print(f"\n{time.perf_counter() - started:.0f} s wall clock with {args.jobs} jobs")
    return 1 if any(verdict(r) == "fail" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
