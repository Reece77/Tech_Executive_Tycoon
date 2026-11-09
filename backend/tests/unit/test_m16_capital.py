"""M16 sub-task 6 (formulas.md 31.5): capital actions. Selling a stake keeps control and brings
NCI; a buyout pays the premium and ends it; a carve-out lists the subsidiary; market stakes in
a listed rival pay a rising price, are disclosed at 5%, 10% and 25% and stop at 30%; a venture
investment buys 5-25% at the round's post-money value. Every consolidated period balances."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from tests.unit.test_m16_group_membership import _assert_balanced, _two_brands
from tst.loader import LoadedData
from tst.sim.errors import GroupRuleError
from tst.sim.finance import statements as fs
from tst.sim.group import formulas as gf
from tst.sim.group.capital import (
    BuyOutMinorities,
    BuyStake,
    CarveOut,
    SellStake,
    VentureInvest,
    value_cents,
)
from tst.sim.ledger import ASSOCIATES, CASH, FINANCIAL_INVESTMENTS, NCI
from tst.sim.mna import valuation
from tst.sim.state import owner_at, with_company


def _types(loaded: LoadedData) -> dict[str, str]:
    return {a.code: a.type for a in loaded.game_data.accounts}


def test_selling_a_stake_brings_nci_and_a_buyout_ends_it(loaded: LoadedData) -> None:
    game, a, _ = _two_brands(loaded)
    b, g = loaded.balance, loaded.game_data
    value = value_cents(game.state, a, game.balances, b, g)
    cash = game.balances[(1, CASH)]
    game.act(SellStake(1, a, 3_000))
    price = gf.stake_price_cents(value, 3_000, b.group.private_discount)
    assert game.balances[(1, CASH)] == cash + price
    held = owner_at(game.state, a)
    assert held is not None and held.stake_at() == 7_000
    holders = {e.holder_kind: e.shares for e in game.state.company_cap(a)}
    assert holders["firm"] == 3_000_000 and holders["group"] == 7_000_000
    with pytest.raises(GroupRuleError):  # 51% at least
        game.act(SellStake(1, a, 2_000))
    game.turn()
    _assert_balanced(game, 1)
    sheet = fs.balance_sheet(game.consolidated(1), _types(loaded), game.state.turn - 1)  # type: ignore[arg-type]
    assert sheet.paid_in_equity.get(NCI, 0) > 0
    # buy them back at the premium
    value = value_cents(game.state, a, game.balances, b, g)
    cash = game.balances[(1, CASH)]
    game.act(BuyOutMinorities(1, a))
    assert game.balances[(1, CASH)] == cash - gf.buyout_cents(value, 3_000, b.group.buyout_premium)
    assert owner_at(game.state, a).stake_at() == 10_000  # type: ignore[union-attr]
    assert [e.holder_kind for e in game.state.company_cap(a)] == ["group"]
    game.turn()
    _assert_balanced(game, 1)
    sheet = fs.balance_sheet(game.consolidated(1), _types(loaded), game.state.turn - 1)  # type: ignore[arg-type]
    assert sheet.paid_in_equity.get(NCI, 0) == 0


def test_a_carve_out_lists_the_subsidiary(loaded: LoadedData) -> None:
    game, a, _ = _two_brands(loaded)
    with pytest.raises(GroupRuleError):
        game.act(CarveOut(1, a, 500))  # 10-40%
    game.act(CarveOut(1, a, 2_000))
    assert valuation.is_listed(game.state, a, loaded.game_data)
    game.turn()
    cap = valuation.market_cap_cents(game.state, a, game.balances, loaded.balance, loaded.game_data)
    assert cap is not None and cap > 0
    assert owner_at(game.state, a).stake_at() == 8_000  # type: ignore[union-attr]
    _assert_balanced(game, 1)


def _listed_rival(game) -> int:  # type: ignore[no-untyped-def]
    state, data = game.state, game.loaded.game_data
    return next(
        c.id
        for c in state.rivals()
        if c.parent_id is None and valuation.is_listed(state, c.id, data)
    )


def test_market_stakes_rise_in_price_disclose_and_stop_at_thirty(loaded: LoadedData) -> None:
    game, *_ = _two_brands(loaded)
    target = _listed_rival(game)
    b = loaded.balance
    cap = valuation.market_cap_cents(game.state, target, game.balances, b, loaded.game_data)
    assert cap is not None
    cash = game.balances[(1, CASH)]
    game.act(BuyStake(1, target, 1_000))
    assert game.balances[(1, CASH)] == cash - gf.market_stake_cents(
        cap, 0, 1_000, b.group.stake_impact
    )
    (stake,) = game.state.stakes
    assert stake.disclosed_bp == 1_000 and game.balances[(1, FINANCIAL_INVESTMENTS)] > 0
    game.act(BuyStake(1, target, 2_500))  # past 20%: an associate now
    assert game.balances.get((1, FINANCIAL_INVESTMENTS), 0) == 0
    assert game.balances[(1, ASSOCIATES)] == game.state.stakes[0].carrying_cents
    assert game.state.stakes[0].disclosed_bp == 2_500
    with pytest.raises(GroupRuleError):
        game.act(BuyStake(1, target, 3_500))  # a full offer from 30%
    game.act(BuyStake(1, target, 3_000))
    with pytest.raises(GroupRuleError):
        game.act(BuyStake(1, target, 3_100))


def test_a_venture_investment_buys_a_share_of_a_round(loaded: LoadedData) -> None:
    game, *_ = _two_brands(loaded)
    b, g = loaded.balance, loaded.game_data
    # startups are founded in play: treat an unlisted independent rival as one
    pick = next(
        c
        for c in game.state.rivals()
        if c.parent_id is None
        and not valuation.is_listed(game.state, c.id, g)
        and game.state.staff(c.id)
    )
    game.state = with_company(game.state, replace(pick, is_startup=True))
    state, startup = game.state, pick.id
    pre = value_cents(state, startup, game.balances, b, g)
    cents = round(pre * Fraction(1, 9))  # 10% post-money
    before = game.balances.get((startup, CASH), 0)
    game.act(VentureInvest(1, startup, cents))
    (stake,) = game.state.stakes
    assert stake.kind == "venture" and 900 <= stake.stake_bp <= 1_100
    assert game.balances[(startup, CASH)] == before + cents
    assert any(
        r.observer_company_id == 1
        and r.person_id in {e.person_id for e in game.state.staff(startup)}
        for r in game.state.reveals
    )
    # M26 (37.2): the round's price is shared with the founder's cheques; nothing else moves
    (rnd,) = game.state.startup_rounds
    assert (rnd.company_id, rnd.raised_cents, rnd.post_cents, rnd.source) == (
        startup,
        cents,
        pre + cents,
        "venture",
    )
    with pytest.raises(GroupRuleError):
        game.act(VentureInvest(1, startup, pre * 10))  # far past 25%
