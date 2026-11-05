"""M14 sub-task 6 (formulas.md 28.6): accepting a takeover bid ends the game with an exit;
rivals buy startups through the same deal code."""

from __future__ import annotations

from dataclasses import replace

from tests.helpers import fresh_game
from tests.unit.test_hiring_phases import Game
from tests.unit.test_m13_public import listed
from tst.loader import LoadedData
from tst.sim.finance.captable import fd_shares, person_shares
from tst.sim.markets_public.public import TAKEOVER_OFFER, apply_public_step
from tst.sim.mna import exit as mna_exit
from tst.sim.mna.rivals import rival_deals
from tst.sim.rng import RngFactory
from tst.sim.state import public_of


def test_talks_queue_the_offer_and_accepting_is_an_exit(loaded: LoadedData) -> None:
    b = loaded.balance
    state = listed()
    talks, _ = apply_public_step(state, 1, "takeover_talks", b)
    assert any(q.template_id == TAKEOVER_OFFER for q in talks.queued)
    public = public_of(talks, 1)
    assert public is not None
    sold, logs = apply_public_step(talks, 1, "takeover_accept", b)
    assert sold.ended and sold.save_meta.game_state == "exit"
    assert sold.save_meta.ended_turn == sold.turn
    sale = mna_exit.sale_of(sold, 1)
    assert sale is not None and sale.acquirer_id == mna_exit.buyer_of(talks)
    per_share = round(public.price_cents * (1 + b.public.takeover.premium))
    assert sale.price_cents == per_share * fd_shares(talks, 1)
    (item,) = logs
    assert item.template == "exit_sale"
    founder = talks.founder_of(1)
    assert founder is not None
    proceeds = person_shares(talks, 1, founder.id) * per_share
    assert (
        dict(item.params)["proceeds"].replace("$", "").replace(",", "")[:3]
        == str(proceeds // 100)[:3]
    )


def test_rejecting_keeps_playing(loaded: LoadedData) -> None:
    state = listed()
    after, _ = apply_public_step(state, 1, "takeover_reject", loaded.balance)
    assert not after.ended and mna_exit.sale_of(after, 1) is None


def test_an_incumbent_buys_a_startup_and_integrates_it(loaded: LoadedData) -> None:
    b = loaded.balance
    always = b.model_copy(update={"mna": b.mna.model_copy(update={"rival_rate": 1.0})})
    game = Game(loaded, fresh_game(loaded))
    for _ in range(3):  # Square is founded in March 2010 (entrants.yaml)
        game.turn()
    square = next(c for c in game.state.companies if c.name == "Square")
    assert game.state.turn % 3 == 0 and square.alive
    agreed = rival_deals(game.state, RngFactory(1), game.balances, always, loaded.game_data)
    deals = [d for d in agreed.deals if d.status == "accepted"]
    assert deals and all(d.mode == "integrate" and d.cash_share == 1.0 for d in deals)
    assert all(not agreed.company(d.acquirer_id).is_player for d in deals)
    same = rival_deals(game.state, RngFactory(1), game.balances, always, loaded.game_data)
    assert same.deals == agreed.deals  # seeded on stream rival_mna
    game.state = agreed
    loaded_always = replace(loaded, balance=always)
    game.loaded = loaded_always
    result = game.turn()
    closed = [d for d in game.state.deals if d.status == "closed"]
    assert closed
    for d in closed:
        target = game.state.company(d.target_id)
        assert not target.alive and game.state.company_products(d.target_id) == ()
        assert game.state.staff(d.target_id) == ()
    assert any(i.template == "rival_acquired" for i in result.log_items)


def test_rivals_wait_for_a_quarter(loaded: LoadedData) -> None:
    b = loaded.balance
    always = b.model_copy(update={"mna": b.mna.model_copy(update={"rival_rate": 1.0})})
    state = replace(fresh_game(loaded), turn=1)
    assert rival_deals(state, RngFactory(1), {}, always, loaded.game_data) == state
