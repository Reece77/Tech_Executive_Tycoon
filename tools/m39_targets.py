"""docs/formulas.md 53.4 targets 2-5 (M39), printed with their values (target 1, history holds, is
tests/unit/test_m39_robotics_data.py and every earlier guard; target 5's guards are make
check-timing).

uv run --project backend python tools/m39_targets.py [--seeds 1 2 ... 10] [--jobs N]
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
    from tst.balance import m39

    results = m39.run(tuple(args.seeds), args.jobs)
    print(m39.report(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
