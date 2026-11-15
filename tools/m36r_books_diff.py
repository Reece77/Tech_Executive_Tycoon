"""M36r: the 2010-2025 books of a do-nothing game (M28's history check), entry by entry, so a
branch's books can be compared with main's. `dump` writes them to a JSON file; `diff` prints
every entry that differs and the largest change of any line, in cents.

Usage:
  uv run --project backend python tools/m36r_books_diff.py dump <seed> <out.json>
  uv run --project backend python tools/m36r_books_diff.py diff <main.json> <branch.json>
"""

from __future__ import annotations

import json
import sys
from collections import Counter


def dump(seed: int, out: str) -> None:
    from tst.balance.game import start_game
    from tst.balance.m28 import LAST_HISTORY_TURN, loaded

    game = start_game(loaded(), seed)
    rows = []
    while game.state.turn <= LAST_HISTORY_TURN:
        game.turn()
        assert game.last_result is not None
        for e in game.last_result.ledger_entries:
            rows.append([e.turn, e.company_id, e.memo, [[x.account, x.amount] for x in e.lines]])
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f)


def diff(a: str, b: str) -> int:
    with open(a, encoding="utf-8") as f:
        main = json.load(f)
    with open(b, encoding="utf-8") as f:
        branch = json.load(f)
    print(f"entries: main {len(main)}, branch {len(branch)}")
    changed: Counter[str] = Counter()
    worst = 0
    shown = 0
    for x, y in zip(main, branch, strict=False):
        if x == y:
            continue
        same_shape = x[:3] == y[:3] and [a for a, _ in x[3]] == [a for a, _ in y[3]]
        if same_shape:
            worst = max(worst, *(abs(p[1] - q[1]) for p, q in zip(x[3], y[3], strict=True)))
        changed[x[2].split(":")[0] if same_shape else "SHAPE: " + x[2]] += 1
        if shown < 10:
            print("main  ", x)
            print("branch", y)
            shown += 1
    for memo, n in changed.most_common():
        print(f"{n:6} {memo}")
    print(f"largest change of a line: {worst} cents")
    return 0


if __name__ == "__main__":
    if sys.argv[1] == "dump":
        dump(int(sys.argv[2]), sys.argv[3])
        sys.exit(0)
    sys.exit(diff(sys.argv[2], sys.argv[3]))
