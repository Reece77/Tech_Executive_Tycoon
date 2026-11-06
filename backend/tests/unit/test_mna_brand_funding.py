"""Reece's playtest 3: a kept brand that ran out of cash went bankrupt. The parent now funds
a brand's shortfall up to mna.funding_months of its costs (an intercompany transfer), a brand
losing money for mna.loss_warning_months months running raises a warning, and a brand never
fails while its parent can pay (28.5)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game
from tests.unit.test_mna_deals import _energy, _founder, _game, _id, _reservation
from tst.loader import LoadedData
from tst.sim.finance.insolvency import insolvency
from tst.sim.ledger import CASH, COMMON_EQUITY, INVESTMENT_SUBSIDIARIES
from tst.sim.mna import integration
from tst.sim.mna.deals import BidForCompany, monthly_costs_cents
from tst.sim.state import with_company


def _bought(loaded: LoadedData):  # type: ignore[no-untyped-def]
    game = _game(loaded, fresh_game(loaded))
    zoho = _id(game.state, "Zoho")
    _energy(game)
    game.act(BidForCompany(_founder(game), zoho, _reservation(game, zoho), mode="brand"))
    game.turn()  # closes
    assert game.state.company(zoho).parent_id == 1
    costs = monthly_costs_cents(game.state, zoho, loaded.balance, loaded.game_data)
    return game, zoho, costs


@pytest.mark.parametrize(("short", "parent_cash", "paid"), [(0.5, 10**12, 0.5), (3.0, 10**12, 1.0)])
def test_the_parent_funds_a_shortfall_up_to_a_month(
    loaded: LoadedData, short: float, parent_cash: int, paid: float
) -> None:
    game, zoho, costs = _bought(loaded)
    balances = {**game.balances, (zoho, CASH): -round(short * costs), (1, CASH): parent_cash}
    entries = integration._fund_brands(game.state, balances, loaded.balance, loaded.game_data)
    amount = round(paid * costs)
    lines = {(e.company_id, line.account): line.amount for e in entries for line in e.lines}
    assert lines[(zoho, CASH)] == amount and lines[(zoho, COMMON_EQUITY)] == -amount
    assert lines[(1, INVESTMENT_SUBSIDIARIES)] == amount and lines[(1, CASH)] == -amount
    assert all(sum(line.amount for line in e.lines) == 0 for e in entries)


def test_a_parent_without_cash_funds_nothing(loaded: LoadedData) -> None:
    game, zoho, costs = _bought(loaded)
    balances = {**game.balances, (zoho, CASH): -costs, (1, CASH): 0}
    assert not integration._fund_brands(game.state, balances, loaded.balance, loaded.game_data)


def test_a_brand_never_fails_while_its_parent_can_pay(loaded: LoadedData) -> None:
    game, zoho, costs = _bought(loaded)
    b, d = loaded.balance, loaded.game_data
    state = with_company(game.state, replace(game.state.company(zoho), insolvent_months=9))
    covered = {**game.balances, (zoho, CASH): -5 * costs}
    out, _ = insolvency(state, covered, b, d)
    assert out.company(zoho).alive and out.company(zoho).insolvent_months == 0
    broke = {**covered, (1, CASH): 0}
    out, _ = insolvency(state, broke, b, d)
    assert not out.company(zoho).alive  # the parent cannot pay: it fails as any rival


def test_a_short_brand_survives_turn_after_turn(loaded: LoadedData) -> None:
    game, zoho, costs = _bought(loaded)
    game.balances[(zoho, CASH)] = -5 * costs  # deep in the red
    for _ in range(loaded.balance.bankruptcy.months + 2):
        game.turn()
    assert game.state.company(zoho).alive
    assert game.balances[(zoho, CASH)] > -5 * costs  # the parent has been paying in


def test_three_losing_months_raise_one_warning(loaded: LoadedData) -> None:
    game, zoho, _ = _bought(loaded)
    months = loaded.balance.mna.loss_warning_months
    later = replace(game.state, turn=game.state.turn + months + 2)

    def warn(history: tuple[int, ...]) -> list[str]:
        state = with_company(later, replace(later.company(zoho), op_history=history))
        return [
            str(dict(i.params)["title"]) for i in integration._loss_warnings(state, loaded.balance)
        ]

    assert warn((5, -1, -1, -1)) == [f"Zoho has lost money for {months} months"]
    assert warn((-1, -1, -1, -1)) == []  # one warning per streak
    assert warn((-1, -1, 5)) == []


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(short=st.integers(0, 10**12), parent=st.integers(-(10**9), 10**12))
def test_funding_always_balances_and_never_overdraws(
    loaded: LoadedData, short: int, parent: int
) -> None:
    game, zoho, costs = _FIXED.setdefault("bought", _bought(loaded))
    balances = {**game.balances, (zoho, CASH): -short, (1, CASH): parent}
    entries = integration._fund_brands(game.state, balances, loaded.balance, loaded.game_data)
    assert all(sum(line.amount for line in e.lines) == 0 for e in entries)
    paid = sum(
        line.amount
        for e in entries
        for line in e.lines
        if (e.company_id, line.account) == (zoho, CASH)
    )
    assert 0 <= paid <= min(short, costs, max(parent, 0))


_FIXED: dict[str, tuple] = {}  # type: ignore[type-arg]
