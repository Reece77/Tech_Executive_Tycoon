"""The balance runner's PR smoke test (M7a, D4a): every strategy plays 24 turns on 2 seeds
without an exception, the books stay balanced, and the same seed gives the same run. The
full 10 x 120 run is `test_balance_targets.py` (nightly) and `make balance`."""

from __future__ import annotations

from collections import defaultdict

import pytest

from tst.balance.game import start_game
from tst.balance.report import evaluate, play, run_all
from tst.balance.strategies import STRATEGIES
from tst.loader import LoadedData

SMOKE_TURNS = 24
SMOKE_SEEDS = (1, 2)


@pytest.mark.parametrize("strategy", list(STRATEGIES))
def test_strategy_plays_and_books_balance(loaded: LoadedData, strategy: str) -> None:
    for seed in SMOKE_SEEDS:
        game = start_game(loaded, seed)
        for _ in range(SMOKE_TURNS):
            if game.state.ended:
                break
            STRATEGIES[strategy](game)
            game.turn()
        per_company: dict[int, int] = defaultdict(int)
        for (company, _account), cents in game.balances.items():
            per_company[company] += cents
        assert all(total == 0 for total in per_company.values()), per_company
        assert len(game.founder_value) == game.state.turn + 1 or game.state.ended


def test_strategies_do_what_they_say(loaded: LoadedData) -> None:
    """do-nothing hires nobody and builds nothing; the others build a product and hire."""
    nothing = play("do-nothing", 1, SMOKE_TURNS)
    assert not nothing.tenures and nothing.launch_turn is None and not nothing.rounds
    for strategy in ("bootstrap-frugal", "steady", "blitzscale"):
        run = play(strategy, 1, SMOKE_TURNS)
        assert run.tenures, strategy
        assert run.launch_turn is not None, strategy
    assert "seed" in play("blitzscale", 1, SMOKE_TURNS).rounds


def test_same_seed_same_run() -> None:
    a, b = play("steady", 2, SMOKE_TURNS), play("steady", 2, SMOKE_TURNS)
    assert (a.value_mean, a.arr_cents, a.rounds, a.tenures, a.events) == (
        b.value_mean,
        b.arr_cents,
        b.rounds,
        b.tenures,
        b.events,
    )


def test_report_has_every_target() -> None:
    rows = evaluate(run_all(seeds=(1,), turns=SMOKE_TURNS, jobs=1))
    targets = {r.target for r in rows}
    assert {"T1", "T2", "T3", "T4a", "T4b", "T4c", "T5", "T6", "T7", "T8", "E3", "S2"} <= targets
