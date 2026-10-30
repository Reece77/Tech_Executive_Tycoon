"""The balance runner (spec §16, docs/balance-targets.md): plays the v1 strategies on fixed
seeds over the pure sim and prints every target with its measured value. Exits 1 when a
pass/fail target (T1-T3) fails, or any target with --strict.

    uv run --project backend python tools/balance_runner.py            # 4 x 10 x 120, + T5 runs
    uv run --project backend python tools/balance_runner.py --turns 24 --seeds 1 2
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
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 11)))
    parser.add_argument("--turns", type=int, default=120)
    parser.add_argument("--strategies", nargs="+", default=None)
    parser.add_argument("--no-difficulty", action="store_true", help="skip T5's easy/hard runs")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--runs", action="store_true", help="also print one line per run")
    parser.add_argument("--strict", action="store_true", help="exit 1 if any band fails too")
    args = parser.parse_args()

    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance.report import evaluate, run_all, runs_table, table
    from tst.balance.strategies import STRATEGIES

    strategies = args.strategies or list(STRATEGIES)
    unknown = set(strategies) - set(STRATEGIES)
    if unknown:
        parser.error(f"unknown strategies {sorted(unknown)}; choose from {list(STRATEGIES)}")
    started = time.perf_counter()
    results = run_all(
        seeds=args.seeds,
        turns=args.turns,
        strategies=strategies,
        difficulty_runs=not args.no_difficulty,
        jobs=args.jobs,
    )
    rows = evaluate(results)
    if args.runs:
        print(runs_table(results), end="\n\n")
    print(table(rows))
    print(
        f"\n{len(results)} runs x {args.turns} turns in {time.perf_counter() - started:.0f} s "
        f"wall clock with {args.jobs} jobs"
    )
    failed = [r for r in rows if r.ok is False and (r.gate or args.strict)]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
