"""docs/formulas.md 20.5 targets 2-5 (M10), printed by tools/m10_targets.py and checked
nightly (tests/balance/test_m10_balance.py).

- Target 2 (debt saves dilution): steady raising a Series B, then either a Series C (arm
  "equity") or the most venture debt the Series B allows instead (arm "debt"); founder
  ownership and bankruptcy at turn 120.
- Target 3 (covenants bite sometimes): blitzscale taking the most venture debt after each
  priced round; the share of seeds with a covenant breach by turn 120.
- Target 4 (the future varies): the macro layer alone over 2026-2039 on 50 seeds.
- Target 5 (later rounds happen): blitzscale that also raises Series C and D when allowed.

The numbers here describe the scripts, not the game, as in strategies.py.
"""

from __future__ import annotations

import statistics
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Final

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.report import SCENARIO, _loaded
from tst.balance.strategies import blitzscale, fundraise, steady
from tst.sim.actions import TakeLoan
from tst.sim.calendar import ym_to_turn
from tst.sim.finance import debt, macro
from tst.sim.finance.captable import founder_bp
from tst.sim.rng import RngFactory

SEEDS: Final = tuple(range(1, 11))
MACRO_SEEDS: Final = tuple(range(1, 51))
TURNS: Final = 120
STEADY_LATER: Final = {"b": 1_500_000_000}  # $15M Series B (both arms)
STEADY_C: Final = {"c": 5_000_000_000}  # $50M Series C (equity arm)
BLITZ_LATER: Final = {"c": 5_000_000_000, "d": 10_000_000_000}  # $50M C, $100M D


@dataclass(frozen=True, slots=True)
class CapitalRun:
    seed: int
    arm: str
    founder_bp: int
    bankrupt: bool
    breached: bool
    # M15a (30.7 V7): a breach in a month whose closing cash was still positive
    breached_positive: bool
    series: tuple[str, ...]  # closed rounds, in order
    loans: int


def take_max_venture_debt(game: Game) -> None:
    """The most venture debt the latest round allows, once it is offered."""
    b, data = game.loaded.balance, game.loaded.game_data
    t = debt.terms(game.state, PLAYER, "venture_debt", b, data)
    if t.problem is None and t.max_cents >= b.debt.min_cents:
        game.act(TakeLoan(game.founder_id, "venture_debt", t.max_cents))


def _closed(game: Game) -> tuple[str, ...]:
    rounds = sorted(
        (r for r in game.state.company_rounds(PLAYER) if r.status == "closed"),
        key=lambda r: (r.closed_turn or 0, r.id),
    )
    return tuple(r.series for r in rounds)


def _play(seed: int, arm: str) -> CapitalRun:
    game = start_game(_loaded("data"), seed, SCENARIO)
    positive = False
    for _ in range(TURNS):
        if game.state.ended:
            break
        if arm in ("equity", "debt"):
            later = {**STEADY_LATER, **(STEADY_C if arm == "equity" else {})}
            fundraise(game, later, pick="pre")
            if arm == "debt" and "b" in _closed(game):
                take_max_venture_debt(game)
            steady(game)
        elif arm == "blitz_debt":
            blitzscale(game)
            take_max_venture_debt(game)
        else:  # blitz_later
            fundraise(game, BLITZ_LATER, pick="amount")
            blitzscale(game)
        before = sum(x.breaches for x in game.state.company_loans(PLAYER))
        game.turn()
        after = sum(x.breaches for x in game.state.company_loans(PLAYER))
        if after > before and game.cash > 0:
            positive = True
    loans = game.state.company_loans(PLAYER)
    return CapitalRun(
        seed=seed,
        arm=arm,
        founder_bp=0 if game.state.ended else founder_bp(game.state, PLAYER),
        bankrupt=game.state.save_meta.game_state == "bankrupt",
        breached=any(x.breaches for x in loans),
        breached_positive=positive,
        series=_closed(game),
        loans=len(loans),
    )


ARMS: Final = ("equity", "debt", "blitz_debt", "blitz_later")


def _job(args: tuple[int, str]) -> CapitalRun:
    return _play(*args)


def run(
    arms: tuple[str, ...] = ARMS, seeds: tuple[int, ...] = SEEDS, jobs: int = 1
) -> list[CapitalRun]:
    work = [(s, a) for a in arms for s in seeds]
    if jobs <= 1:
        return [_job(w) for w in work]
    with ProcessPoolExecutor(jobs) as pool:
        return list(pool.map(_job, work))


@dataclass(frozen=True, slots=True)
class MacroFuture:
    seeds: int
    with_downturn: int
    climate_2030_sd: float


def macro_future(seeds: tuple[int, ...] = MACRO_SEEDS) -> MacroFuture:
    """Target 4: over 2026-2039, how many seeds see a downturn, and the spread of the venture
    climate in December 2030."""
    loaded = _loaded("data")
    last = ym_to_turn(2039, 12)
    mark = ym_to_turn(2030, 12)
    downturns = 0
    climates = []
    for seed in seeds:
        rng = RngFactory(seed)
        prev = None
        hit = False
        for turn in range(last + 1):
            prev = macro.month_for(turn, prev, rng, loaded.balance, loaded.game_data)
            hit |= prev.downturn_turn is not None
            if turn == mark:
                climates.append(prev.climate)
        downturns += hit
    return MacroFuture(len(seeds), downturns, statistics.pstdev(climates))


def median_bp(runs: list[CapitalRun], arm: str) -> float:
    return statistics.median(r.founder_bp for r in runs if r.arm == arm)


def share(runs: list[CapitalRun], arm: str, test: str) -> float:
    mine = [r for r in runs if r.arm == arm]
    return sum(bool(getattr(r, test)) for r in mine) / len(mine)


def reached(runs: list[CapitalRun], arm: str, series: str) -> int:
    return sum(series in r.series for r in runs if r.arm == arm)
