"""docs/formulas.md 41.8 targets (M28), printed with their values.

uv run --project backend python tools/m28_targets.py [--seeds 1 2 ... 10] [--jobs N]
uv run --project backend python tools/m28_targets.py --write-history   # on a checkout of main
uv run --project backend python tools/m28_targets.py --check-history   # target 1 only
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
    parser.add_argument("--write-history", action="store_true")
    parser.add_argument("--check-history", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import m28

    if args.write_history:
        m28.write_history(m28.history_all(tuple(args.seeds), args.jobs))
        print(f"wrote {m28.HISTORY_FILE}")
        return 0
    if args.check_history:
        diffs = m28.history_diffs(
            m28.history_all(tuple(args.seeds), args.jobs), m28.recorded_history()
        )
        print("\n".join(diffs) if diffs else "history holds on every seed")
        return 1 if diffs else 0
    print(m28.report(m28.run(tuple(args.seeds), args.jobs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
