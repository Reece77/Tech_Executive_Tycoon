"""M54's balance targets (docs/formulas.md 64.6): tst.balance.m54, printed.

uv run --project backend python tools/m54_targets.py [--seeds 1-10] [--workers 4]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from tst.balance import m54


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", default="1-10")
    p.add_argument("--workers", type=int, default=4)
    a = p.parse_args()
    lo, _, hi = a.seeds.partition("-")
    seeds = tuple(range(int(lo), int(hi or lo) + 1))
    print(m54.report(m54.run(seeds, a.workers)))


if __name__ == "__main__":
    main()
