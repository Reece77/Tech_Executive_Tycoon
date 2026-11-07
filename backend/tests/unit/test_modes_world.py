"""M15b sub-task 2: a start in year Y has the world a 2010 game has in year Y on the same seed
(macro, components and eras), with the player's company founded that month."""

from __future__ import annotations

import pytest

from tests.helpers import DEFAULT_FOUNDER, fresh_game
from tests.unit.test_hiring_phases import Game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.ledger import CASH, apply_entries
from tst.sim.modes.world import ModeSpec, start_mode
from tst.sim.rng import RngFactory
from tst.sim.setup import new_game

SEED = 3


def _new(loaded: LoadedData):  # type: ignore[no-untyped-def]
    return new_game(
        save_name="t",
        master_seed=SEED,
        scenario=loaded.game_data.scenario("ex_big_tech_founders"),  # type: ignore[arg-type]
        difficulty="standard",
        company_name="Kestrel",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
    )


@pytest.fixture(scope="module")
def started_2013(loaded: LoadedData):  # type: ignore[no-untyped-def]
    state, entries = _new(loaded)
    spec = ModeSpec(kind="sandbox", start_year=2013, cash_cents=5_000_000_00)
    return start_mode(
        state, entries, spec, DEFAULT_FOUNDER, RngFactory(SEED), loaded.balance, loaded.game_data
    )


def test_a_2013_start_has_the_2013_world(loaded: LoadedData, started_2013) -> None:  # type: ignore[no-untyped-def]
    world, _ = started_2013
    game = Game(loaded, fresh_game(loaded, seed=SEED), cash=10**15)  # a dormant 2010 game
    while game.state.turn < ym_to_turn(2013, 1):
        game.turn()
    assert world.turn == game.state.turn
    assert world.macro == game.state.macro
    assert world.supply == game.state.supply
    assert world.era_arrivals == game.state.era_arrivals
    assert world.listings == game.state.listings
    rivals = {c.id: c for c in game.state.rivals()}
    assert all(c == rivals[c.id] for c in world.rivals())  # the rivals as they stood


def test_the_company_is_founded_in_the_start_month(loaded: LoadedData, started_2013) -> None:  # type: ignore[no-untyped-def]
    world, entries = started_2013
    start = ym_to_turn(2013, 1)
    player = world.player
    assert player.founded_turn == start and player.mrr_history == ()
    founder = world.founder_of(player.id)
    assert founder is not None
    assert next(e for e in world.employments if e.person_id == founder.id).start_turn == start
    balances = apply_entries({}, entries)
    assert balances[(player.id, CASH)] == 5_000_000_00  # exactly the chosen cash
    assert all(sum(ln.amount for ln in e.lines) == 0 for e in entries)
    assert not [e for e in world.events if e.company_id == player.id]
    assert world.mode is not None and world.mode.start_turn == start
    assert any(balances.get((c.id, CASH), 0) for c in world.rivals())  # rivals keep their cash


def test_no_rivals_closes_every_rival(loaded: LoadedData) -> None:
    state, entries = _new(loaded)
    spec = ModeSpec(kind="sandbox", start_year=2010, rivals="none")
    world, _ = start_mode(
        state, entries, spec, DEFAULT_FOUNDER, RngFactory(SEED), loaded.balance, loaded.game_data
    )
    others = [c for c in world.companies if not c.is_player]
    assert others and not world.rivals()  # every rival closed
    spec = ModeSpec(kind="sandbox", start_year=2010, rivals="half")
    half, _ = start_mode(
        state, entries, spec, DEFAULT_FOUNDER, RngFactory(SEED), loaded.balance, loaded.game_data
    )
    alive = len(half.rivals())
    assert 0.35 * len(others) <= alive <= 0.65 * len(others)
