"""docs/formulas.md 19.8 targets 2, 3 and 5 (M9), printed with their values.

uv run --project backend python tools/m9_targets.py                     # all three, 10 seeds
uv run --project backend python tools/m9_targets.py --arms spread --seeds 1 2
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
EXPANSION_NEEDED = 1.4  # 19.8 target 2
SAVING_NEEDED = 0.5  # 19.8 target 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 11)))
    parser.add_argument("--arms", nargs="+", default=["expansion", "team", "spread"])
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import m9
    from tst.sim.money import format_money

    failed = False
    seeds = tuple(args.seeds)
    if "expansion" in args.arms:
        results = m9.run_expansion(seeds, args.jobs)
        for r in results:
            print(f"  expansion seed {r.seed}: abroad {format_money(r.arr_a)}, home {format_money(r.arr_b)}")
        value = m9.expansion_ratio(results)
        ok = value >= EXPANSION_NEEDED
        failed |= not ok
        print(
            "Target 2: blitzscale turn-120 ARR, launching in Europe and East Asia / home only: "
            f"{value:.3f} (needs >= {EXPANSION_NEEDED}) {'PASS' if ok else 'FAIL'}"
        )
    if "team" in args.arms:
        cost = m9.team_cost()
        ok = cost.saving >= SAVING_NEEDED and cost.split_factor < 1
        failed |= not ok
        print(
            f"Target 3: 30 engineers a month, San Francisco {format_money(cost.sf_cents)}, "
            f"Bangalore {format_money(cost.bangalore_cents)}: {cost.saving:.1%} less "
            f"(needs >= {SAVING_NEEDED:.0%}); split team factor x{cost.split_factor:.2f} "
            f"{'PASS' if ok else 'FAIL'}"
        )
    if "spread" in args.arms:
        spreads = m9.run_spread(seeds, args.jobs)
        for s in spreads:
            print(f"  spread seed {s.seed}: {s.covered}/{s.total}; missing {list(s.missing)}")
        ok = all(not s.missing for s in spreads)
        failed |= not ok
        print(
            "Target 5: every region has a live rival product in each category at turn 120 "
            f"(do-nothing): {sum(not s.missing for s in spreads)}/{len(spreads)} seeds "
            f"{'PASS' if ok else 'FAIL'}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
