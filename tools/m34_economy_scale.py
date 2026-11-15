"""Derive balance.yaml's `economy_scale.money` (M34, PM ruling 2026-11-15): the designated
incumbents' in-game 2025 booked revenue over their real 2025 revenue, on do-nothing games.

Real 2025 revenue (US dollars): Apple $416.2B (fiscal year to September 2025), Microsoft
$281.7B (fiscal year to June 2025; the game's Microsoft and Microsoft Azure together), Meta
$200.97B (calendar 2025; the game's Facebook). Sources in balance.yaml's economy_scale.

Usage: uv run --project backend python tools/m34_economy_scale.py [--seeds 1-3] [--workers N]
"""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor

REAL_CENTS = {
    "Apple": 416_200_000_000_00,
    "Microsoft": 281_700_000_000_00,
    "Facebook": 200_970_000_000_00,
}
GROUPS = {
    "Apple": ("Apple",),
    "Microsoft": ("Microsoft", "Microsoft Azure"),
    "Facebook": ("Facebook",),
}
YEAR_2025 = range(180, 192)


def one(seed: int) -> dict[str, int]:
    from tst.balance.game import start_game
    from tst.balance.m28 import loaded
    from tst.sim.regulation.measure import booked_revenue

    game = start_game(loaded(), seed)
    names = {c.id: c.name for c in game.state.companies}
    total: dict[str, int] = {k: 0 for k in GROUPS}
    while game.state.turn < YEAR_2025.stop:
        turn = game.state.turn
        game.turn()
        if turn in YEAR_2025 and game.last_result is not None:
            month = booked_revenue(game.last_result.ledger_entries, game.loaded.game_data)
            for cid, cents in month.items():
                for key, members in GROUPS.items():
                    if names.get(cid) in members:
                        total[key] += cents
    return total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="1-3")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    lo, _, hi = args.seeds.partition("-")
    seeds = list(range(int(lo), int(hi or lo) + 1))
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(one, seeds))
    ratios = []
    for key, real in REAL_CENTS.items():
        game = sum(r[key] for r in results) / len(results)
        ratios.append(game / real)
        print(
            f"{key:10s} in game ${game / 1e11:8.2f}B  real ${real / 1e11:7.2f}B"
            f"  ratio {game / real:.4f}"
        )
    print(f"economy_scale.money = {sum(ratios) / len(ratios):.4f} (mean of the three ratios)")


if __name__ == "__main__":
    main()
