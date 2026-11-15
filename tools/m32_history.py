"""docs/formulas.md 46.8 target 1 (M32): history holds.

uv run --project backend python tools/m32_history.py --write   # on a checkout of main (before M32)
uv run --project backend python tools/m32_history.py           # on the branch: compare
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
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import m32_history as h

    runs = h.history_all(seeds=tuple(args.seeds), workers=args.jobs)
    if args.write:
        h.write_history(runs)
        print(f"wrote {h.HISTORY_FILE}")
        return 0
    want = h.recorded_history()
    costs, books = h.cost_diffs(runs, want), h.book_diffs(runs, want)
    for line in costs:
        print(f"power cost over 1%: {line}")
    for line in books:
        print(f"books differ: {line}")
    if not costs and not books:
        print("history holds: every kind's power cost within 1% and the books identical")
    return 1 if costs or books else 0


if __name__ == "__main__":
    raise SystemExit(main())
