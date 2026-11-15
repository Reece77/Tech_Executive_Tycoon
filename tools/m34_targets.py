"""Print M34's balance targets (docs/formulas.md 48.5) on seeds 1-10.

Usage: uv run --project backend python tools/m34_targets.py [--seeds 1-10] [--workers N]
"""

from __future__ import annotations

import argparse
import os

from tst.balance import m34


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="1-10")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    results = m34.run(seeds, args.workers)
    for r in results:
        print(r)
    print(m34.report(results))


if __name__ == "__main__":
    main()
