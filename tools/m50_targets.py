"""Print M50's balance targets (docs/formulas.md 60.3, targets 2-4) on seeds 1-10.

Usage: uv run --project backend python tools/m50_targets.py [--seeds 1-10] [--workers N]
       [--no-strategies] (targets 2-3 only)
"""

from __future__ import annotations

import argparse
import os

from tst.balance import m50


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="1-10")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--no-strategies", action="store_true")
    args = parser.parse_args()
    lo, _, hi = args.seeds.partition("-")
    seeds = tuple(range(int(lo), int(hi or lo) + 1))
    print(m50.report(seeds, args.workers, strategies=not args.no_strategies))


if __name__ == "__main__":
    main()
