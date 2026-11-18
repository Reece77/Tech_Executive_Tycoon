"""M45's long state-cache check (tst.balance.m45): play M37's dynasty game (full_integrator,
family, dynasty mode on) on seeds 1-3 for 720 months in memory and compare every month's
full-state digest with backend/tests/fixtures/m45_dynasty_hashes.json, or with `--write` record
them (only on code whose results are the reference: the fixture was made before any M45 change).

    uv run --project backend python tools/m45_state_hashes.py [--write] [--workers N]
"""

from __future__ import annotations

import argparse
import os
import sys
import time


def main() -> int:
    from tst.balance import m30, m45

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="record the fixture")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--turns", type=int, default=m45.TURNS)
    args = parser.parse_args()
    started = time.perf_counter()
    got = m45.all_hashes(args.workers, args.turns)
    print(
        f"{len(got)} runs, {sum(map(len, got.values()))} months in "
        f"{time.perf_counter() - started:.0f} s"
    )
    if args.write:
        m45.write(got)
        print(f"wrote {m45.HASH_FILE}")
        return 0
    want = m45.recorded()
    bad = 0
    for name, months in sorted(got.items()):
        diff = m30.first_difference(months, want.get(name, [])[: args.turns])
        print(f"{name}: {'identical' if diff is None else diff}")
        bad += diff is not None
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
