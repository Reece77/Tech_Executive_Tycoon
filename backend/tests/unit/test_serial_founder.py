"""Serial founder (M15b addendum 10): after an exit, found a new company or retire. The world
carries on unchanged for rivals; the founder's cash and stake are right; a second exit works."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game
from tests.unit.test_hiring_phases import Game
from tst.loader import LoadedData
from tst.sim.actions.hiring import OpenSearch
from tst.sim.errors import GameOverError, InvalidModeError
from tst.sim.finance.captable import fd_shares, person_shares
from tst.sim.ledger import CASH
from tst.sim.mna.exit import buyer_of
from tst.sim.mna.models import Deal
from tst.sim.modes.serial import FoundAgain, Retire, proceeds_cents
from tst.sim.state import GameState

PRICE = 400_000_000_00  # $400M for every share
KEEP = 50_000_000_00  # the founder keeps $50M


def _exited(state: GameState) -> GameState:
    """The player's company sold to the largest rival this month (28.6), as sell_company
    leaves it."""
    buyer = buyer_of(state)
    assert buyer is not None
    deal_id, ids = state.next_ids.take("deal")
    deal = Deal(
        id=deal_id,
        acquirer_id=buyer,
        target_id=state.player.id,
        price_cents=PRICE,
        cash_share=1.0,
        made_turn=state.turn,
        status="closed",
        resolved_turn=state.turn,
        mode="integrate",
    )
    meta = replace(state.save_meta, game_state="exit", ended_turn=state.turn)
    return replace(state, next_ids=ids, deals=(*state.deals, deal), save_meta=meta)


def _game(loaded: LoadedData) -> Game:
    game = Game(loaded, fresh_game(loaded))
    for _ in range(2):
        game.turn()
    game.state = _exited(game.state)
    return game


def _founder(game: Game) -> int:
    founder = game.state.founder_of(game.state.player.id)
    assert founder is not None
    return founder.id


def _rivals_world(state: GameState, skip: set[int]) -> tuple[object, ...]:
    return (
        tuple(c for c in state.companies if not c.is_player and c.id not in skip),
        tuple(p for p in state.products if p.company_id not in skip),
        state.product_segments,
        state.markets,
        tuple(e for e in state.employments if e.company_id not in skip),
        state.research_leads,
        state.era_arrivals,
    )


def test_actions_are_refused_until_a_choice(loaded: LoadedData) -> None:
    game = _game(loaded)
    with pytest.raises(GameOverError):
        game.act(OpenSearch(_founder(game), "software_engineer", "job_post"))
    with pytest.raises(InvalidModeError):  # not more than the proceeds
        game.act(FoundAgain(_founder(game), "Again", keep_cents=PRICE))


def test_found_again_cash_stake_and_world(loaded: LoadedData) -> None:
    game = _game(loaded)
    old = game.state.player
    founder = _founder(game)
    proceeds = proceeds_cents(game.state, old.id)
    shares = person_shares(game.state, old.id, founder)
    assert proceeds == PRICE * shares // fd_shares(game.state, old.id) and proceeds > KEEP
    before = game.state
    game.act(FoundAgain(founder, "Second Act", keep_cents=KEEP))
    state = game.state
    new = state.player
    assert new.id != old.id and new.name == "Second Act" and new.founded_turn == state.turn
    assert not state.ended and state.save_meta.game_state == "active"
    # the founder's cash and stake
    assert game.balances[(new.id, CASH)] == proceeds - KEEP
    assert state.founder_of(new.id) is not None
    assert person_shares(state, new.id, founder) == 9_000_000
    assert fd_shares(state, new.id) == loaded.balance.finance.initial_fd_shares
    # the founder keeps their stats; the sold company is a brand of its buyer
    assert state.person(founder) == before.person(founder)
    sold = state.company(old.id)
    buyer = buyer_of(before)
    assert not sold.is_player and sold.parent_id == buyer and sold.alive
    assert not any(e.person_id == founder for e in state.staff(old.id))
    (venture,) = state.ventures
    assert (venture.company_id, venture.buyer_id, venture.proceeds_cents) == (
        old.id,
        buyer,
        proceeds,
    )
    assert venture.kept_cents == KEEP
    # the rivals' world is untouched
    assert _rivals_world(state, {old.id, new.id}) == _rivals_world(before, {old.id})
    # and carries on: the new company plays months, the old one runs as a rival's brand
    for _ in range(3):
        game.turn()
    assert game.state.player.id == new.id
    assert game.state.company(old.id).alive
    assert game.balances[(new.id, CASH)] > 0


def test_a_second_exit_works(loaded: LoadedData) -> None:
    game = _game(loaded)
    first = game.state.player.id
    game.act(FoundAgain(_founder(game), "Second Act", keep_cents=KEEP))
    game.turn()
    game.state = _exited(game.state)
    second = game.state.player.id
    game.act(FoundAgain(_founder(game), "Third Act"))
    state = game.state
    assert [v.company_id for v in state.ventures] == [first, second]
    assert state.player.name == "Third Act" and state.player.id not in (first, second)
    assert game.balances[(state.player.id, CASH)] == state.ventures[1].proceeds_cents


def test_retire_ends_the_game(loaded: LoadedData) -> None:
    game = _game(loaded)
    game.act(Retire(_founder(game)))
    assert game.state.save_meta.game_state == "retired" and game.state.ended
    assert len(game.state.ventures) == 1
    with pytest.raises(InvalidModeError):
        game.act(Retire(_founder(game)))


def test_a_new_venture_has_a_stable_identity(loaded: LoadedData) -> None:
    """M15r (Codex review 4 finding 9): the new venture's draws (IPO demand, sentiment, deals,
    press) follow a persisted venture key, not its database id, so appending an unrelated
    company before founding again changes none of them."""
    from tst.sim.markets_public import ipo
    from tst.sim.markets_public.public import sentiment_draws
    from tst.sim.mna.deals import key_of
    from tst.sim.rivals.models import player_key
    from tst.sim.rng import RngFactory
    from tst.sim.state import CompanyState

    game = _game(loaded)
    plain = game.state
    extra = CompanyState(
        id=max(c.id for c in plain.companies) + 1,
        name="Unrelated Co",
        is_player=False,
        stage=0,
        founded_turn=0,
    )
    appended = replace(plain, companies=(*plain.companies, extra))
    rng = RngFactory(3)
    out = []
    for state in (plain, appended):
        founder = state.founder_of(state.player.id)
        assert founder is not None
        from tst.sim.modes.serial import found_again

        new, _, _ = found_again(state, "Second Act", KEEP, rng, loaded.balance, loaded.game_data)
        company = new.player
        key = player_key(company.id, company.rival_key)
        out.append(
            (
                company.id,
                key,
                key_of(new, company.id),
                ipo.draw_demand(rng, 60, key, 1.0, loaded.balance),
                float(sentiment_draws(rng, 60, *key).random()),
            )
        )
    (id_a, *draws_a), (id_b, *draws_b) = out
    assert id_a != id_b  # the database ids differ...
    assert draws_a == draws_b  # ...and nothing the venture draws does
    assert out[0][1] == (4, 1)  # VENTURE_KEY, the second company the player has run
