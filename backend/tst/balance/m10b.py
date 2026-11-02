"""docs/formulas.md 23.7 target 1 (M10b), printed by tools/m10b_targets.py and checked nightly
(tests/balance/test_m10b_balance.py): the steady strategy on 10 seeds x 120 turns; critical
events per 18 months of the months the company had 20 or more staff, and the shortest gap
between two critical events.

The numbers here describe the script, not the game, as in strategies.py.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from itertools import pairwise
from typing import Final

from tst.balance.game import PLAYER, start_game
from tst.balance.report import SCENARIO, _loaded
from tst.balance.strategies import steady

SEEDS: Final = tuple(range(1, 11))
TURNS: Final = 120
STAFF: Final = 20  # 23.7: companies with 20+ staff
WINDOW: Final = 18  # months: at least one critical event per this many


@dataclass(frozen=True, slots=True)
class CrisisRun:
    seed: int
    big_months: int  # months ended with 20+ staff
    criticals: tuple[tuple[int, str], ...]  # (turn shown, trigger) of every critical event
    big_criticals: int  # those shown in a month that began with 20+ staff
    shortest_gap: int | None


def _play(seed: int) -> CrisisRun:
    game = start_game(_loaded("data"), seed, SCENARIO)
    big: set[int] = set()
    for _ in range(TURNS):
        if game.state.ended:
            break
        steady(game)
        if len(game.state.staff(PLAYER)) >= STAFF:
            big.add(game.state.turn)
        game.turn()
    events = sorted(
        (e.turn, e.trigger)
        for e in game.state.events
        if e.company_id == PLAYER and e.severity == "critical"
    )
    turns = [t for t, _ in events]
    gaps = [b - a for a, b in pairwise(turns)]
    return CrisisRun(
        seed=seed,
        big_months=len(big),
        criticals=tuple(events),
        big_criticals=sum(1 for t in turns if t in big),
        shortest_gap=min(gaps) if gaps else None,
    )


def run(seeds: tuple[int, ...] = SEEDS, jobs: int = 1) -> list[CrisisRun]:
    if jobs <= 1:
        return [_play(s) for s in seeds]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(_play, seeds))


def per_window(runs: list[CrisisRun]) -> float:
    """Critical events per 18 months with 20+ staff, over all seeds together."""
    months = sum(r.big_months for r in runs)
    return sum(r.big_criticals for r in runs) / months * WINDOW if months else 0.0
