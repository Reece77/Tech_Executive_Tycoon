"""Insolvency, bridges and bankruptcy (formulas.md 14.7, ADR-0018) and stages from funding
(14.8), through turns."""

from __future__ import annotations

import pytest

from tests.helpers import fresh_game, make_person, move_directors, with_employee
from tests.unit.test_hiring_phases import Game
from tst.loader import LoadedData
from tst.sim.actions import AcceptBridge
from tst.sim.errors import FinanceRuleError, GameOverError
from tst.sim.ledger import CASH, account_balance

FOUNDER = 1
SALARY = 12_000_000  # $10,000 a month


def broke_game(loaded: LoadedData, scenario: str) -> Game:
    state = move_directors(fresh_game(loaded, scenario=scenario))
    state = with_employee(loaded, state, make_person(loaded, 2), SALARY)
    return Game(loaded, state, cash=-100)


def templates(game: Game) -> list[str]:
    return [i.template or "" for r in game.results for i in r.log_items]


def test_three_months_below_zero_is_bankruptcy(loaded: LoadedData) -> None:
    game = broke_game(loaded, "garage_bootstrap")  # no board, so no bridge
    for month in (1, 2):
        game.turn()
        assert game.state.player.insolvent_months == month and not game.state.ended
    game.turn()
    assert (game.state.save_meta.game_state, game.state.save_meta.ended_turn) == ("bankrupt", 2)
    assert templates(game).count("insolvent") == 3 and templates(game)[-2:] != []
    assert "bankrupt" in templates(game) and "bridge_offered" not in templates(game)
    with pytest.raises(GameOverError):
        game.turn()


def test_a_bridge_accepted_in_time_prevents_bankruptcy(loaded: LoadedData) -> None:
    game = broke_game(loaded, "funded_spinout")  # First Round sits on the board at 70
    game.turn()
    (bridge,) = game.state.safes
    assert (bridge.kind, bridge.status, bridge.expires_turn) == ("bridge", "offered", 2)
    assert bridge.cap_cents == round(0.8 * 750_000_000)  # 0.8 x the $7.5M post-money
    assert bridge.amount_cents >= 3 * SALARY // 12  # three months of this month's burn
    assert "bridge_offered" in templates(game)
    game.act(AcceptBridge(FOUNDER, bridge.id))
    game.turn()  # the money arrives in phase 7 of the month it is accepted
    assert game.state.safes[0].status == "outstanding"
    assert account_balance(game.balances, 1, CASH) > 0
    assert game.state.player.insolvent_months == 0
    assert "bridge_funded" in templates(game)
    for _ in range(2):
        game.turn()
    assert not game.state.ended  # three months of burn covered the gap


def test_one_bridge_offer_per_insolvency(loaded: LoadedData) -> None:
    game = broke_game(loaded, "funded_spinout")
    game.turn()
    game.turn()  # month 2 below zero: no second offer in the same insolvency
    assert len(game.state.safes) == 1 and game.state.player.insolvent_months == 2


def test_an_unaccepted_bridge_lapses(loaded: LoadedData) -> None:
    game = broke_game(loaded, "funded_spinout")
    game.turn()
    bridge = game.state.safes[0]
    game.balances = {**game.balances, (1, CASH): 100_000_000}  # solvent again another way
    for _ in range(3):
        game.turn()
    assert game.state.safes[0].status == "lapsed"
    assert "bridge_lapsed" in templates(game)
    with pytest.raises(FinanceRuleError, match="no longer open"):
        game.act(AcceptBridge(FOUNDER, bridge.id))


def test_a_closed_seed_lifts_stage_1_to_2(loaded: LoadedData) -> None:
    state = move_directors(fresh_game(loaded, scenario="funded_spinout"))
    state = with_employee(loaded, state, make_person(loaded, 2), SALARY)  # a first hire
    game = Game(loaded, state, cash=150_000_000)
    game.turn()
    assert game.state.player.stage == 2  # stage 1 from the hire, then 2 from the seed
    assert "stage_from_funding" in templates(game)
