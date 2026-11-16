"""M35b (sub-task 4): Google Play's regulated rates (platforms.yaml, the EU from March 2024 and
the US from October 2025) against the same game without them. Prints, year by year, the
2010-2025 books entries that differ: every one must be a platform-fee entry, and every
company's net revenue must be equal (the fees are calibrated: tools/m31_history_diff.py). This
is the diff behind re-recording M28's history fingerprint (41.8 target 1) for the fee series.

Usage: uv run --project backend python tools/m35b_play_diff.py [seed]
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import replace

from tst.balance.game import start_game
from tst.balance.m28 import LAST_HISTORY_TURN, loaded
from tst.loader import LoadedData
from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.ledger import PLATFORM_FEES, REVENUE_SUBSCRIPTIONS

FEE_MEMOS = ("Platform fees", "Platform fees earned", "Store price calibration")
NEW_ROWS = {("android_play", "eu", "2024-03"), ("android_play", "united_states", "2025-10")}

type Entry = tuple[int, int, str, tuple[tuple[str, int], ...]]


def without_rows(data: LoadedData) -> LoadedData:
    pf = data.game_data.platforms
    assert pf is not None
    rules = tuple(r for r in pf.fee_rules if (r.platform, r.part, r.from_) not in NEW_ROWS)
    assert len(rules) == len(pf.fee_rules) - len(NEW_ROWS)
    gd = data.game_data.model_copy(update={"platforms": pf.model_copy(update={"fee_rules": rules})})
    return replace(data, game_data=gd)


def books(data: LoadedData, seed: int) -> list[Entry]:
    game = start_game(data, seed)
    out: list[Entry] = []
    while game.state.turn <= LAST_HISTORY_TURN:
        game.turn()
        assert game.last_result is not None
        for e in game.last_result.ledger_entries:
            out.append(
                (e.turn, e.company_id, e.memo, tuple((x.account, x.amount) for x in e.lines))
            )
    return out


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    base, new = books(without_rows(loaded()), seed), books(loaded(), seed)
    only_base = Counter(base) - Counter(new)
    only_new = Counter(new) - Counter(base)
    bad = [e for e in (*only_base, *only_new) if not e[2].startswith(FEE_MEMOS)]
    print(f"seed {seed}: entries only without the rows: {sum(only_base.values())}; only with "
          f"them: {sum(only_new.values())}; not platform-fee entries: {len(bad)}")  # fmt: skip
    for e in bad[:10]:
        print("  not a fee entry:", e)
    print("year  entries changed  5150 fees paid, with - without")
    for year in range(2010, 2026):
        a = [e for e in only_new if 2010 + e[0] // MONTHS_PER_YEAR == year]
        b = [e for e in only_base if 2010 + e[0] // MONTHS_PER_YEAR == year]
        fees = sum(x for e in a for acct, x in e[3] if acct == PLATFORM_FEES) - sum(
            x for e in b for acct, x in e[3] if acct == PLATFORM_FEES
        )
        if a or b:
            print(f"{year}  {len(a) + len(b):15d}  ${fees / 100:>+26,.0f}")

    def net(entries: list[Entry]) -> Counter[int]:
        t: Counter[int] = Counter()
        for _turn, cid, _memo, lines in entries:
            for acct, x in lines:
                if acct in (REVENUE_SUBSCRIPTIONS, PLATFORM_FEES):
                    t[cid] -= x
        return t

    nb, nn = net(base), net(new)
    worst = max((abs(nn[c] - nb[c]) / nb[c] for c in nb if nb[c] > 0), default=0.0)
    print(f"largest change in a company's 2010-2025 net revenue: {worst:.4%}")


if __name__ == "__main__":
    main()
