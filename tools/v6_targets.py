"""Print M57's v6 strategy targets (docs/tasks/M57-v6-balance-and-polish.md, sub-task 4;
tst.balance.v6). Exits 1 if a target misses beyond a recorded known miss.

uv run --project backend python tools/v6_targets.py              # v6 and v5's field, 20 seeds
uv run --project backend python tools/v6_targets.py --seeds 1 2 --save runs.json
uv run --project backend python tools/v6_targets.py --load a.json b.json   # combine saved shards
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
    parser.add_argument("--strategies", nargs="+", default=None)
    parser.add_argument("--save", type=Path, default=None, help="write the runs as JSON")
    parser.add_argument("--load", type=Path, nargs="+", default=None, help="read saved runs")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    save = args.save.resolve() if args.save else None
    load = [p.resolve() for p in args.load] if args.load else None

    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import v6
    from tst.balance.known_misses import verdict
    from tst.balance.report import table

    started = time.perf_counter()
    if load:
        runs = [r for p in load for r in v6.load(p)]
    else:
        names = args.strategies or v6.PLAYED
        seeds = args.seeds or list(v6.SEEDS)
        runs = v6.run_all(names, seeds, jobs=args.jobs)
    if save:
        v6.save(runs, save)
    print(v6.run_table(runs), end="\n\n")
    print(v6.strategy_table(runs), end="\n\n")
    rows = v6.rows(runs)
    print(table(rows))
    print(f"\n{time.perf_counter() - started:.0f} s wall clock with {args.jobs} jobs")
    return 1 if any(verdict(r) == "fail" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
