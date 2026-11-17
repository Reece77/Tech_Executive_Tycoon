"""Print M37's formulas.md 52.5 targets 2-4 (ten dynasty games to December 2069; about twice a
360-turn run each). Long: dispatch the nightly workflow instead of running this locally for
more than an hour (CLAUDE.md 9 rule 7).

    uv run --project backend python tools/m37_targets.py [--jobs 4] [--seeds 1-10]
"""

from __future__ import annotations

import argparse

from tst.balance import m37


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--seeds", default="1-10")
    args = parser.parse_args()
    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    print(m37.report(m37.run_all(args.jobs, seeds)))


if __name__ == "__main__":
    main()
