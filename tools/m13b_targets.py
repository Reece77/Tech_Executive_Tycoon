"""docs/formulas.md 27.5 targets 1-5 (M13b), printed with their values.

uv run --project backend python tools/m13b_targets.py
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
    from tst.balance import m13b

    results = m13b.run(tuple(args.seeds), args.jobs)
    print(m13b.report(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
