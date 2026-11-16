"""M35b: the v4 scripts (tst.balance.strategies_v4) on short runs; the targets themselves are
weekly (tests/balance/test_v4_balance.py)."""

from __future__ import annotations

from tst.balance import strategies_v4 as v4
from tst.balance.game import PLAYER, start_game
from tst.balance.report import SCENARIO
from tst.balance.v3 import loaded
from tst.sim.calendar import ym_to_turn


def test_platform_owner_launches_its_os_by_2014() -> None:
    game = start_game(loaded(), 1, SCENARIO)
    while game.state.turn <= ym_to_turn(2014, 12):
        v4.platform_owner(game)
        game.turn()
    assert v4.rung(game, "os") is not None and v4.rung(game, "os") <= ym_to_turn(2014, 12)
    platform = v4.own_platform(game)
    assert platform is not None
    p = game.state.platform(platform)
    assert p is not None and p.owner_id == PLAYER and p.kind == "device"


def test_every_v4_script_plays_a_year() -> None:
    for name, script in {**v4.V4, **v4.V4_ARMS}.items():
        game = start_game(loaded(), 2, SCENARIO)
        for _ in range(12):
            script(game)
            game.turn()
        assert not game.state.ended, name


def test_litho_funding_is_the_60th_percentile() -> None:
    game = start_game(loaded(), 1, SCENARIO)
    f = game.loaded.balance.equipment.programme.funding
    assert v4.litho_funding(game) == f.lo + 0.6 * (f.hi - f.lo)
