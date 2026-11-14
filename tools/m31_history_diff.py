"""M31 (44.9 target 1, Reece 2026-11-14): the 2010-2025 books with fees from 2010 against the
same game with fees from 2026 (main's books to 2025). Prints, year by year, the entries that
differ: every one must be a platform-fee entry (a seller's cash-neutral gross-up, or an owner's
fees earned), and every app-category company's net revenue must be equal.

Usage: uv run --project backend python tools/m31_history_diff.py [seed]
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import replace

from tst.balance.game import start_game
from tst.balance.m28 import LAST_HISTORY_TURN, loaded
from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.ledger import PLATFORM_FEE_REVENUE, PLATFORM_FEES, REVENUE_SUBSCRIPTIONS

FEE_MEMOS = ("Platform fees", "Platform fees earned")


def books(fees_from: str, seed: int) -> list[tuple[int, int, str, tuple[tuple[str, int], ...]]]:
    data = loaded()
    pb = data.balance.platforms.model_copy(update={"fees_from": fees_from})
    data = replace(data, balance=data.balance.model_copy(update={"platforms": pb}))
    game = start_game(data, seed)
    out = []
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
    base, fees = books("2026-01", seed), books("2010-01", seed)
    only_base = Counter(base) - Counter(fees)
    only_fees = Counter(fees) - Counter(base)
    print(f"seed {seed}: entries only without fees: {sum(only_base.values())}")
    bad = [e for e in only_fees if not e[2].startswith(FEE_MEMOS)]
    print(
        f"entries only with fees: {sum(only_fees.values())}; not platform-fee entries: {len(bad)}"
    )
    print("year  fee entries  gross-up (5150 = 4000 credit)  owners' 4150")
    for year in range(2010, 2026):
        rows = [e for e in only_fees if 2010 + e[0] // MONTHS_PER_YEAR == year]
        grossup = sum(a for e in rows for acct, a in e[3] if acct == PLATFORM_FEES)
        earned = -sum(a for e in rows for acct, a in e[3] if acct == PLATFORM_FEE_REVENUE)
        print(f"{year}  {len(rows):11d}  ${grossup / 100:>28,.0f}  ${earned / 100:>12,.0f}")

    def net(entries):  # type: ignore[no-untyped-def]
        t: Counter[int] = Counter()
        for _turn, cid, _memo, lines in entries:
            for acct, a in lines:
                if acct == REVENUE_SUBSCRIPTIONS:
                    t[cid] -= a
                if acct == PLATFORM_FEES:
                    t[cid] -= a
        return t

    nb, nf = net(base), net(fees)
    worst = max((abs(nf[c] - nb[c]) / nb[c] for c in nb if nb[c] > 0), default=0.0)
    print(f"largest change in a company's 2010-2025 net revenue: {worst:.4%}")


if __name__ == "__main__":
    main()
