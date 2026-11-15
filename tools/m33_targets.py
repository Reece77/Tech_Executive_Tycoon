"""Print M33's balance targets (docs/formulas.md 47.5) on seeds 1-10.

Usage: uv run --project backend python tools/m33_targets.py [--seeds 1-10] [--workers N]
"""

from __future__ import annotations

import argparse
import os

from tst.balance import m33


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="1-10")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    print(m33.report(m33.run_all(seeds, args.workers)))


if __name__ == "__main__":
    main()
