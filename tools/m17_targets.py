"""docs/formulas.md 33.6 targets (M17), printed with their values.

uv run --project backend python tools/m17_targets.py [--seeds 1 2 ...]
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
    args = parser.parse_args()
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import m17

    print(m17.report(m17.run(tuple(args.seeds))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
