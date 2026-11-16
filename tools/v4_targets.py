"""Print M35b's v4 balance targets (docs/tasks/M35b-v4-balance.md; tst.balance.v4). Exits 1 if a
target misses beyond a recorded known miss.

uv run --project backend python tools/v4_targets.py            # T1-T4, every strategy, 10 seeds
uv run --project backend python tools/v4_targets.py --v4-only  # the runs T1, T3 and T4 read
uv run --project backend python tools/v4_targets.py --seeds 11 12 --save runs.json
uv run --project backend python tools/v4_targets.py --load a.json b.json   # combine saved shards
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
    parser.add_argument("--v4-only", action="store_true", help="skip T2's v3 field")
    parser.add_argument("--save", type=Path, default=None, help="write the runs as JSON")
    parser.add_argument("--load", type=Path, nargs="+", default=None, help="read saved runs")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    save = args.save.resolve() if args.save else None
    load = [p.resolve() for p in args.load] if args.load else None

    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import v4
    from tst.balance.known_misses import verdict
    from tst.balance.report import table

    started = time.perf_counter()
    if load:
        runs = [r for p in load for r in v4.load(p)]
    else:
        names = args.strategies or (v4.V4_ONLY if args.v4_only else v4.PLAYED)
        runs = v4.run_all(names, args.seeds or list(v4.SEEDS), jobs=args.jobs)
    if save:
        v4.save(runs, save)
    print(v4.run_table(runs), end="\n\n")
    print(v4.rung_table([r for r in runs if r.rungs]), end="\n\n")
    rows = v4.rows(runs)
    for decade in sorted({(r.seed - 1) // 10 for r in runs}):
        part = [r for r in runs if (r.seed - 1) // 10 == decade]
        if len({r.seed for r in runs}) > 10:
            print(f"seeds {decade * 10 + 1}-{decade * 10 + 10}:\n{table(v4.rows(part))}\n")
    print(table(rows))
    print(f"\n{time.perf_counter() - started:.0f} s wall clock with {args.jobs} jobs")
    return 1 if any(verdict(r) == "fail" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
