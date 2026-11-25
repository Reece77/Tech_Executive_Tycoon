"""Print M51's 63.4 targets 1 and 2 (tst.balance.m51): every scenario played by the sensible and
passive scripts on seeds 1-10, and each challenge rule's effect on the scripted score.

Usage: uv run --project backend python tools/m51_targets.py [workers]
"""

from __future__ import annotations

import sys

from tst.balance import m51


def main() -> None:
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    runs = m51.run_table(m51.NEW + m51.FIVE, workers=workers)
    for r in runs:
        print(r.key, r.script, r.seed, r.result, r.result_turn, r.score, r.note, flush=True)
    rows = m51.target_2(workers=workers)
    print(m51.report(runs, rows))
    raise SystemExit(0 if m51.met(runs, rows) else 1)


if __name__ == "__main__":
    main()
