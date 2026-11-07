"""Print docs/formulas.md 28.9's targets (M14). A tool: reads true values.

uv run --project backend python tools/m14_targets.py --jobs 4
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 11)))
    parser.add_argument("--save", default="", help="also pickle the raw results here")
    args = parser.parse_args()
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import m14

    import pickle

    results = m14.run(tuple(args.seeds), jobs=args.jobs)
    if args.save:
        Path(args.save).write_bytes(pickle.dumps(results))
    print(m14.report(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
