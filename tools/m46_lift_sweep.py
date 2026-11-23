"""M46: M27a's 40.10 targets and M46's listed-capital target with balance overrides (CI only;
`make m46-lift SET="products.marketer_lift=0.03 products.marketer_lift_cap=0.3"`).

    uv run --project backend python tools/m46_lift_sweep.py [key=value ...]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m46_overrides import BACKEND, overridden_data


def main(settings: list[str]) -> int:
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    sys.path.insert(0, str(BACKEND))
    jobs = os.cpu_count() or 1
    with overridden_data(settings) as root:
        os.chdir(root)  # the balance scripts load "data" from the working directory
        from tst.balance import m27, m46

        runs = m46.run(m46.SEEDS, jobs)
        for r in sorted(runs, key=lambda r: (r.seed, r.strategy)):
            print(f"seed {r.seed:2d} {r.strategy:15} ARR ${r.arr_cents / 1e8:7.1f}M", flush=True)
        print(f"M46 listed capital: median paired {1 + m46.paired_lift(runs):.3f}x", flush=True)
        print(m27.report(m27.run(m27.SEEDS, jobs)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
