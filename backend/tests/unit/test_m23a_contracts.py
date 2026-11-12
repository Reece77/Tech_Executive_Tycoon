"""M23a sub-task 6 (playtest 5): every contract can be terminated at a quoted fee (the remaining
months' take-or-pay minimum discounted at the base rate, plus contracts.break_penalty), the
counterparty remembers; a fab signs foundry contracts with rival designers; offtakes and own
supply keep 100% allocation in shortages."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from tst.balance import m21, m22
from tst.balance.game import Game, start_game
from tst.sim.actions.commodities import SignCommodityContract, SignOfftake
from tst.sim.calendar import ym_to_turn
from tst.sim.commodities import costs, offtake
from tst.sim.contracts import termination as ct
from tst.sim.contracts.termination import TerminateContract
from tst.sim.fabs import market as fm
from tst.sim.fabs.foundry import SignFoundryContract, customers
from tst.sim.ledger import CASH, FOUNDRY_SALES, GENERAL_ADMIN
from tst.sim.state import with_person_state

RICH = 10**13


def _game(ym: tuple[int, int] = (2016, 1)) -> Game:
    g = start_game(m22.loaded(), 1, "funded_spinout")
    g.state = replace(g.state, turn=ym_to_turn(*ym))
    g.balances[(1, CASH)] = g.balances.get((1, CASH), 0) + RICH
    return g


def _energy(g: Game) -> None:
    g.state = with_person_state(g.state, replace(g.state.person_state(g.founder_id), energy=100))


def _reference_fee(monthly: Fraction, months: int, base_pct: float, penalty: float) -> int:
    """Independent: sum of monthly / (1 + r/12)^k for k = 1..months, x (1 + penalty)."""
    r = Fraction(str(base_pct)) / 100 / 12
    pv = sum(monthly / (1 + r) ** k for k in range(1, months + 1))
    return round(pv * (1 + Fraction(str(penalty))))


def test_terminating_a_commodity_contract_costs_its_quoted_fee() -> None:
    lg = m22.loaded()
    b, d = lg.balance, lg.game_data
    g = _game()
    _energy(g)
    assert g.act(SignCommodityContract(g.founder_id, "copper", 24, 1_200.0)), dict(g.refused)
    deal = g.state.commodity_deals[-1]
    for _ in range(3):
        g.turn()
    q = ct.quote(g.state, "commodity", deal.id, b, d)
    months = deal.end_turn - g.state.turn + 1
    assert q.months_left == months > 0
    monthly = Fraction(str(b.commodity.contract_take_or_pay)) * Fraction(
        repr(offtake.value_cents(deal.monthly_volume, deal.signing_price, "copper", d))
    )
    assert g.state.macro is not None
    expected = _reference_fee(monthly, months, g.state.macro.base_rate, b.contracts.break_penalty)
    assert q.fee_cents == expected and q.cash_cents == expected
    cash, ga = g.cash, g.balances.get((1, GENERAL_ADMIN), 0)
    _energy(g)
    assert g.act(TerminateContract(g.founder_id, "commodity", deal.id)), dict(g.refused)
    assert cash - g.cash == expected
    assert g.balances.get((1, GENERAL_ADMIN), 0) - ga == expected
    ended = next(x for x in g.state.commodity_deals if x.id == deal.id)
    assert not ended.running(g.state.turn)
    # the market remembers: a new contract is dearer
    assert ct.score(g.state, "traders:copper", b) == 1 - Fraction(str(b.contracts.relationship_hit))
    assert ct.premium(g.state, "traders:copper", b) > 1


def test_an_offtakes_prepayment_counts_against_the_fee_and_the_supplier_remembers() -> None:
    lg = m22.loaded()
    b, d = lg.balance, lg.game_data
    g = _game()
    _energy(g)
    assert g.act(SignOfftake(g.founder_id, "copper", "freeport", 5, 1_200.0, 0.05)), dict(g.refused)
    deal = g.state.commodity_deals[-1]
    assert deal.prepaid_left_cents > 0
    g.turn()
    deal = next(x for x in g.state.commodity_deals if x.id == deal.id)
    q = ct.quote(g.state, "commodity", deal.id, b, d)
    assert q.prepaid_cents == deal.prepaid_left_cents
    assert q.cash_cents == q.fee_cents - deal.prepaid_left_cents
    before = offtake.offtake_quote(g.state, "copper", "freeport", 5, 1_200.0, 0.0, b, d).price
    _energy(g)
    assert g.act(TerminateContract(g.founder_id, "commodity", deal.id)), dict(g.refused)
    after = offtake.offtake_quote(g.state, "copper", "freeport", 5, 1_200.0, 0.0, b, d).price
    assert after == pytest.approx(before * float(ct.premium(g.state, "freeport", b)))
    assert after > before
    # three breaks in a row and the supplier will not sign again for now
    for _ in range(2):
        _energy(g)
        assert g.act(SignOfftake(g.founder_id, "copper", "freeport", 3, 100.0, 0.0))
        _energy(g)
        assert g.act(TerminateContract(g.founder_id, "commodity", g.state.commodity_deals[-1].id))
    _energy(g)
    assert not g.act(SignOfftake(g.founder_id, "copper", "freeport", 3, 100.0, 0.0))


def test_a_wafer_contract_and_a_refinery_contract_can_be_terminated() -> None:
    from tst.balance import m12b
    from tst.sim.refining.actions import SignRefiningDeal

    lg = m22.loaded()
    b, d = lg.balance, lg.game_data
    m12b._loaded = lambda: lg  # type: ignore[assignment]
    g, _ = m12b.device_company(1, own_chip=True, start=ym_to_turn(2016, 1))
    g.balances[(1, CASH)] = g.balances.get((1, CASH), 0) + RICH
    wafer = next(c for c in g.state.production_contracts if c.kind == "wafer")
    q = ct.quote(g.state, "production", wafer.id, b, d)
    monthly = Fraction(str(b.chips.contract.take_or_pay)) * Fraction(
        wafer.units * wafer.price_millicents, 1000
    )
    base = g.state.macro.base_rate if g.state.macro is not None else 0.0  # unplayed: no month
    assert q.fee_cents == _reference_fee(monthly, q.months_left, base, b.contracts.break_penalty)
    _energy(g)
    assert g.act(TerminateContract(g.founder_id, "production", wafer.id)), dict(g.refused)
    assert not next(c for c in g.state.production_contracts if c.id == wafer.id).running(
        g.state.turn
    )
    _energy(g)
    assert g.act(SignRefiningDeal(g.founder_id, "buy", "polysilicon", 12, 100.0)), dict(g.refused)
    deal = g.state.refining_deals[-1]
    assert ct.quote(g.state, "refining", deal.id, b, d).fee_cents > 0
    _energy(g)
    assert g.act(TerminateContract(g.founder_id, "refining", deal.id))
    assert next(x for x in g.state.refining_deals if x.id == deal.id).status == "ended"


# --- Foundry contracts -------------------------------------------------------------------------


def test_a_fab_sells_contracted_starts_before_spot_slots() -> None:
    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    game = m21.game_at(1, ym_to_turn(2016, 1))
    fid = m21.build(game, "n28", "east_asia", 10_000)
    fab = fm.fab_of(game.state, fid)
    assert fab is not None
    slot = fm.node_price_cents(game.state, "n28", b, d) * b.fab.slot.discount
    who = customers(d)[0]
    _energy(game)
    too_dear = SignFoundryContract(game.founder_id, fid, who, 2_000, 12, slot * 1.5)
    assert not game.act(too_dear)
    _energy(game)
    too_big = SignFoundryContract(game.founder_id, fid, who, 5_000, 12, slot)
    assert not game.act(too_big)  # one designer takes at most 40% of 10,000
    _energy(game)
    assert game.act(SignFoundryContract(game.founder_id, fid, who, 3_000, 12, slot)), dict(
        game.refused
    )
    before = game.balances.get((1, FOUNDRY_SALES), 0)
    m21.play(game, 1)
    fab = fm.fab_of(game.state, fid)
    assert fab is not None and fab.month is not None
    m = fab.month
    assert m.contracted == pytest.approx(3_000)
    assert m.sold > m.contracted  # spare starts beyond the contract still sell at spot
    assert (who, pytest.approx(3_000)) in [(n, pytest.approx(v)) for n, v in m.customers][:1]
    assert -(game.balances.get((1, FOUNDRY_SALES), 0) - before) == m.revenue_cents
    c = game.state.foundry_contracts[-1]
    assert c.delivered == pytest.approx(3_000)
    q = ct.quote(game.state, "foundry", c.id, b, d)
    assert q.counterparty == who and q.fee_cents > 0


def test_foundry_contracts_raise_a_fabs_use() -> None:
    lg = m21.loaded()
    b, d = lg.balance, lg.game_data
    plain = m21.game_at(1, ym_to_turn(2016, 1))
    fid = m21.build(plain, "n28", "east_asia", 10_000)
    signed = m21.game_at(1, ym_to_turn(2016, 1))
    fid2 = m21.build(signed, "n28", "east_asia", 10_000)
    slot = fm.node_price_cents(signed.state, "n28", b, d) * b.fab.slot.discount
    for who in customers(d)[:2]:
        _energy(signed)
        assert signed.act(SignFoundryContract(signed.founder_id, fid2, who, 4_000, 24, slot))
    m21.play(plain, 2)
    m21.play(signed, 2)
    use = [fm.fab_of(g.state, f).month.utilization for g, f in ((plain, fid), (signed, fid2))]  # type: ignore[union-attr]
    assert use[1] > use[0]


# --- Offtakes and own supply protect production -------------------------------------------------


def test_an_offtake_signed_in_a_shortage_keeps_full_allocation() -> None:
    from tst.sim.commodities.models import CommodityDeal

    d = m22.loaded().game_data
    deal = CommodityDeal(1, 1, "offtake", "lithium", 100, 200, 120.0, 10.0, 8.0, 12.0, "albemarle")
    assert costs.protected(deal, start=90)  # signed after the shortage began, not prepaid
    contract = replace(deal, kind="contract", supplier=None)
    assert not costs.protected(contract, start=90)
    assert costs.protected(contract, start=110)
    assert d is not None
