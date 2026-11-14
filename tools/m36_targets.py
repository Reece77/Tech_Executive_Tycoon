"""Print M36's formulas.md 45.8 targets (tst.balance.m36). Usage:
uv run --project backend python tools/m36_targets.py [--jobs N] [--only time,upbringing,succession,estate]
"""

from __future__ import annotations

import argparse

from tst.balance import m36


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--only", default="")
    parser.add_argument("--seeds", type=int, default=10)
    args = parser.parse_args()
    only = tuple(x for x in args.only.split(",") if x)
    results = m36.run(tuple(range(1, args.seeds + 1)), jobs=args.jobs, only=only)
    print(m36.report(results))
    for r in results.succession:
        print(f"  seed {r.seed}: heir ${r.heir_cents / 100:,.0f}  ceo ${r.ceo_cents / 100:,.0f}")
    for e in results.estate:
        print(f"  seed {e.seed}: stake {e.stake:.1%} lost {e.lost_plain} trust {e.lost_trust}")


if __name__ == "__main__":
    main()
