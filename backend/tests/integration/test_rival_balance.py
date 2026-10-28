"""M5 balance targets (formulas.md 15.7), printed and checked on 10 seeds."""

from __future__ import annotations

from tests.balance_scripts import start
from tests.integration.test_market_balance import served_shares
from tst.loader import LoadedData

SEEDS = range(1, 11)
LIVING_TURNS = 120


def test_living_market(loaded: LoadedData) -> None:
    """1. With no player product, over 120 turns, no incumbent's share of a segment's served
    customers falls below half or rises above double its starting share."""
    worst_low, worst_high, breaches = 1.0, 1.0, 0
    for seed in SEEDS:
        run = start(loaded, seed)
        incumbents = {p.id for p in run.state.products}
        first = {k: v for k, v in served_shares(run.state).items() if k[2] in incumbents}
        for _ in range(LIVING_TURNS):
            run.turn()
            now = served_shares(run.state)
            for key, share in first.items():
                if share < 1.0:  # under a point to start: too small to judge
                    continue
                ratio = now.get(key, 0.0) / share
                worst_low, worst_high = min(worst_low, ratio), max(worst_high, ratio)
                if not 0.5 <= ratio <= 2.0:
                    breaches += 1
                    break
        print(f"seed {seed}: worst share ratio so far {worst_low:.2f} to {worst_high:.2f}")
    print(f"living market: breaches {breaches}, ratios {worst_low:.2f} to {worst_high:.2f}")
    assert breaches == 0
