"""docs/formulas.md 18.9 targets 2, 3 and 5 (M8), printed with their values.

uv run --project backend python tools/m8_targets.py                # all three, 10 seeds
uv run --project backend python tools/m8_targets.py --arms seats --seeds 1 2
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
NEEDED = {"seats": 1.15, "support": 1.08, "blitz": 1.2}
LABELS = {
    "seats": "Target 2: ARR with six seats filled / all vacant, 36 months after stage 3",
    "support": "Target 3: ARR at coverage 1.0 / 0.5, 36 months after stage 3",
    "blitz": "Target 5: blitzscale turn-120 ARR, second product in Fintech / standard",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 11)))
    parser.add_argument("--arms", nargs="+", default=list(NEEDED))
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import m8
    from tst.sim.money import format_money

    failed = False
    for arm in args.arms:
        results = m8.run(arm, tuple(args.seeds), args.jobs)
        for r in results:
            print(
                f"  {arm} seed {r.seed}: fork turn {r.stage_3_turn}, "
                f"A {format_money(r.arr_a)}, B {format_money(r.arr_b)}"
            )
        value = m8.ratio(results)
        ok = value >= NEEDED[arm]
        failed |= not ok
        print(f"{LABELS[arm]}: {value:.3f} (needs >= {NEEDED[arm]}) {'PASS' if ok else 'FAIL'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
