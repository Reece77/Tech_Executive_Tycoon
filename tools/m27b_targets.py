"""M27b's chain targets (a), (b) and (d) (docs/formulas.md 40.7; target (c) is a property test
and is counted here too), printed with their values.

uv run --project backend python tools/m27b_targets.py --seeds 1 2 3 --jobs 4 > m27b.txt
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
    parser.add_argument("--fork", type=int, default=180, help="turn the arms start (180)")
    parser.add_argument("--end", type=int, default=360, help="turn they end (360)")
    args = parser.parse_args()
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import m27b

    results = m27b.run(tuple(args.seeds), args.jobs, args.fork, args.end)
    print(m27b.report(results), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
