"""M10d (product manager, 2026-11-02): the player loses 0.5-1.5 staff a year to rivals while
the company has 30 or more people (median over 10 seeds, steady and blitzscale, 120 turns).
Checked nightly by tests/balance/test_m10d_balance.py; docs/formulas.md 15.7 target 6.

The numbers here describe the scripts, not the game, as in strategies.py.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from statistics import median
from typing import Final

from tst.balance.game import PLAYER, start_game
from tst.balance.report import SCENARIO, _loaded
from tst.balance.strategies import STRATEGIES

SEEDS: Final = tuple(range(1, 11))
TURNS: Final = 120
STAFF: Final = 30
STRATEGY_NAMES: Final = ("steady", "blitzscale")
MIN_MONTHS: Final = 12  # a seed counts once it has a year with 30+ staff
MONTHS_PER_YEAR: Final = 12


@dataclass(frozen=True, slots=True)
class LossRun:
    strategy: str
    seed: int
    big_months: int  # months that began with 30+ staff
    poached: int  # employees who left for a rival in those months

    @property
    def per_year(self) -> float | None:
        if self.big_months < MIN_MONTHS:
            return None
        return self.poached / (self.big_months / MONTHS_PER_YEAR)


def _play(job: tuple[str, int]) -> LossRun:
    name, seed = job
    game = start_game(_loaded("data"), seed, SCENARIO)
    big: set[int] = set()
    for _ in range(TURNS):
        if game.state.ended:
            break
        STRATEGIES[name](game)
        if len(game.state.staff(PLAYER)) >= STAFF:
            big.add(game.state.turn)
        game.turn()
    poached = sum(
        1
        for e in game.state.employments
        if e.company_id == PLAYER
        and e.end_reason == "poached"
        and e.end_turn is not None
        and (e.end_turn in big or e.end_turn - 1 in big)
    )
    return LossRun(name, seed, len(big), poached)


def run(seeds: tuple[int, ...] = SEEDS, jobs: int = 1) -> list[LossRun]:
    work = [(n, s) for n in STRATEGY_NAMES for s in seeds]
    if jobs <= 1:
        return [_play(w) for w in work]
    with ProcessPoolExecutor(jobs) as pool:
        return list(pool.map(_play, work))


def median_per_year(runs: list[LossRun], strategy: str) -> float | None:
    values = [r.per_year for r in runs if r.strategy == strategy and r.per_year is not None]
    return median(values) if values else None
