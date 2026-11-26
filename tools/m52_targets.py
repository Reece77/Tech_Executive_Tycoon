"""Print M52's 66.4 targets (tst.balance.m52): target 2 (every scenario round-trips through the
editor to an identical game, month 12, seeds 1-3) and, with `--long`, target 4 (a 2069 dynasty
game continued in sandbox to December 2100 on seeds 1-3: errors, the largest integer and the
2100 economy against SQLite's int64, and 2100's month times in memory).

Usage: uv run --project backend python tools/m52_targets.py [workers] [--long]
"""

from __future__ import annotations

import sys

from tst.balance import m52


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    workers = int(args[0]) if args else 4
    ok = True
    if "--long" not in sys.argv:
        runs = m52.round_trips(workers=workers)
        for r in runs:
            print(
                f"{r.key:22} seed {r.seed}: {r.months} months, identical {r.identical}"
                + (f" ({r.first_difference})" if r.first_difference else ""),
                flush=True,
            )
        same = sum(r.identical for r in runs)
        print(f"Target 2: {same}/{len(runs)} identical to month {m52.ROUND_TRIP_MONTHS}")
        ok = same == len(runs)
    else:
        for r in m52.long_play(workers=min(workers, len(m52.SEEDS))):
            late = sorted(r.late_ms)
            median = late[len(late) // 2] if late else 0
            print(
                f"seed {r.seed}: to {r.reached} ({r.ended}), error {r.error}; largest integer"
                f" {r.largest_int:.3e} ({m52.INT64 / max(1, r.largest_int):,.0f}x below int64);"
                f" largest balance {r.largest_balance:.3e}; 2100 revenue {r.revenue_2100:.3e}"
                f" cents ({m52.INT64 / max(1, r.revenue_2100):,.0f}x below); 2100 months"
                f" median {median} ms, at most {max(late, default=0)} ms",
                flush=True,
            )
            ok = ok and r.error is None and r.revenue_2100 * m52.ECONOMY_MARGIN < m52.INT64
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
