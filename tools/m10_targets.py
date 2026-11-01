"""docs/formulas.md 20.5 targets 2-5 (M10), printed with their values.

uv run --project backend python tools/m10_targets.py
uv run --project backend python tools/m10_targets.py --arms blitz_debt --seeds 1 2
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
    parser.add_argument("--arms", nargs="+", default=None)
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from tst.balance import m10

    arms = tuple(args.arms) if args.arms else m10.ARMS
    runs = m10.run(arms, tuple(args.seeds), args.jobs)
    for r in runs:
        print(
            f"  {r.arm} seed {r.seed}: founder {r.founder_bp / 100:.1f}%, rounds "
            f"{'/'.join(r.series) or '-'}, loans {r.loans}, breached {r.breached}, "
            f"bankrupt {r.bankrupt}"
        )
    failed = False

    def verdict(label: str, value: str, ok: bool) -> None:
        nonlocal failed
        failed |= not ok
        print(f"{label}: {value} {'PASS' if ok else 'FAIL'}")

    if {"equity", "debt"} <= set(arms):
        gain = (m10.median_bp(runs, "debt") - m10.median_bp(runs, "equity")) / 100
        risk = (m10.share(runs, "debt", "bankrupt") - m10.share(runs, "equity", "bankrupt")) * 100
        verdict(
            "Target 2: founder points, venture debt after B / Series C (median)",
            f"{gain:+.1f} points (needs >= +5), bankruptcy {risk:+.0f} points (needs <= +10)",
            gain >= 5 and risk <= 10,
        )
    if "blitz_debt" in arms:
        rate = m10.share(runs, "blitz_debt", "breached")
        verdict(
            "Target 3: blitzscale with maximum venture debt, seeds with a breach",
            f"{rate:.0%} (needs 20-60%)",
            0.2 <= rate <= 0.6,
        )
    if "blitz_later" in arms:
        count = m10.reached(runs, "blitz_later", "c")
        verdict(
            "Target 5: blitzscale reaching a Series C by turn 120",
            f"{count} of {len(args.seeds)} (needs >= 4)",
            count >= 4,
        )
    future = m10.macro_future()
    verdict(
        "Target 4: 2026-2039 seeds with a downturn; sd of the 2030 venture climate",
        f"{future.with_downturn}/{future.seeds} (needs >= 80%), sd {future.climate_2030_sd:.3f} "
        "(needs >= 0.15)",
        future.with_downturn >= 0.8 * future.seeds and future.climate_2030_sd >= 0.15,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
