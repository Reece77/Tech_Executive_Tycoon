"""docs/formulas.md 58.5 targets 1-5 (M47), printed with their values (tst.balance.m47; target
4 is tests/integration/test_m47_conversations.py; target 5's guards are make check-timing).

uv run --project backend python tools/m47_targets.py [--seeds 1 2 ... 10] [--deals 40]
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
    parser.add_argument("--deals", type=int, default=40)
    args = parser.parse_args()
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import m47

    print(m47.report(tuple(args.seeds), args.deals))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
