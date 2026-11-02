"""docs/formulas.md 23.7 target 1 (M10b), printed with its values.

uv run --project backend python tools/m10b_targets.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 11)))
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import m10b

    runs = m10b.run(tuple(args.seeds), args.jobs)
    for r in runs:
        print(
            f"seed {r.seed:2d}: {r.big_months} months with 20+ staff, {r.big_criticals} "
            f"critical in them; all {list(r.criticals)}; shortest gap {r.shortest_gap}"
        )
    print(f"23.7 target 1: {m10b.per_window(runs):.2f} per 18 months with 20+ staff (>= 1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
