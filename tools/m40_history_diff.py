"""M40's history check (docs/formulas.md 56.4 target 1): M28's fingerprint to December 2025
with M40's space rivals' lines left out, against main's recorded fixture, seed by seed.

Usage: uv run --project backend python tools/m40_history_diff.py [--seeds 1-10] [--workers N]
"""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor

from tst.balance import m28, m40


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="1-10")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    lo, _, hi = args.seeds.partition("-")
    seeds = list(range(int(lo), int(hi or lo) + 1))
    recorded = m28.recorded_history()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        got = dict(zip(seeds, pool.map(m40.history_without_space, seeds), strict=True))
    bad = 0
    for seed in seeds:
        want = recorded[str(seed)]
        diffs = [
            f"{s} {y}"
            for s in m28.SERIES
            if s != m28.SPACE
            for y in want[s]
            if want[s][y] != got[seed][s].get(y)
        ]
        bad += len(diffs)
        print(f"seed {seed}: {'identical' if not diffs else ', '.join(diffs)}")
    print(f"{bad} differences outside M40's own rivals")


if __name__ == "__main__":
    main()
