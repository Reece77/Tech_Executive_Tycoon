"""Print M37's formulas.md 52.5 targets 2-4 (ten dynasty games to December 2069; about twice a
360-turn run each). Long: dispatch the nightly workflow instead of running this locally for
more than an hour (CLAUDE.md 9 rule 7).

    uv run --project backend python tools/m37_targets.py [--jobs 4] [--seeds 1-10]

`--write-reference` (M43r) re-records target 1's mode-parity fixture
(`tests/fixtures/m37_pre_2040_hashes.json`) from the nine standard runs, after checking that the
nine dynasty runs and the nine runs with M37's rules disabled (the same-code differential) equal
them month by month to December 2039; it writes nothing if any differs. Record the reason in
CHANGELOG, as for M30's state cache.
"""

from __future__ import annotations

import argparse

from tst.balance import m37


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--seeds", default="1-10")
    parser.add_argument("--write-reference", action="store_true")
    args = parser.parse_args()
    if args.write_reference:
        raise SystemExit(m37.write_reference(args.jobs))
    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    print(m37.report(m37.run_all(args.jobs, seeds)))


if __name__ == "__main__":
    main()
