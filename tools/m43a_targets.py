"""Print M43a's formulas.md 54.4 targets 1-4 (dynasty games to December 2069, M37's script).
Long: dispatch the nightly workflow instead of running this locally for more than an hour
(CLAUDE.md 9 rule 7).

    uv run --project backend python tools/m43a_targets.py [--jobs 4] [--seeds 1-10] [--turns 720]
"""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path

from tst.balance import m43a


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--seeds", default="1-10")
    parser.add_argument("--turns", type=int, default=m43a.END)
    parser.add_argument("--save", type=Path, default=None, help="pickle the results here")
    args = parser.parse_args()
    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    results = m43a.run_all(args.jobs, seeds, args.turns)
    if args.save:
        args.save.write_bytes(pickle.dumps(results))
    print(m43a.report(results))


if __name__ == "__main__":
    main()
