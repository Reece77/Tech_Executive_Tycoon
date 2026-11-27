"""M55's balance targets (docs/formulas.md 65.8): tst.balance.m55, printed.

uv run --project backend python tools/m55_targets.py [--seeds 1-10] [--workers 4]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from tst.balance import m55  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", default="1-10")
    p.add_argument("--workers", type=int, default=4)
    a = p.parse_args()
    lo, _, hi = a.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    rows = m55.run(tuple(seeds), a.workers)
    for r in rows:
        print(r)
    print(m55.table(rows))


if __name__ == "__main__":
    main()
