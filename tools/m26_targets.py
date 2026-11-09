"""docs/formulas.md 37.6 targets (M26), printed with their values.

uv run --project backend python tools/m26_targets.py [--only 1 3] [--seeds 1 2 3]
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
    parser.add_argument("--only", nargs="+", default=[], help="targets to run: 1 2 3 4 5")
    args = parser.parse_args()
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import m26

    print(m26.report(m26.run(tuple(args.seeds), args.jobs, tuple(args.only))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
