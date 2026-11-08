"""M16 sub-task 7 (formulas.md 31.6, 31.7): transfer prices and the conglomerate discount. One
brand supplies another's compute in-group: the buyer's outside spend is replaced, the seller's
cost is group.supply_cost of it, and consolidation removes the intercompany sale. With
minorities, a price 20% under market for six months raises the complaint, its legal costs run
until the price is fair, and moving to market settles it."""

from __future__ import annotations

from fractions import Fraction

from tests.unit.test_m16_group_membership import _assert_balanced, _two_brands
from tst.loader import LoadedData
from tst.sim.events.models import GameEvent
from tst.sim.finance import statements as fs
from tst.sim.group.capital import SellStake
from tst.sim.group.discount import conglomerate, segments
from tst.sim.group.transfer import (
    COMPLAINT_TEMPLATE,
    SetTransferPrice,
    complaint_against,
    group_step,
)
from tst.sim.ledger import COMPUTE, INTERCOMPANY_PURCHASES, INTERCOMPANY_SALES


def test_a_flow_supplies_in_group_and_consolidation_removes_it(loaded: LoadedData) -> None:
    game, a, b = _two_brands(loaded)
    game.act(SetTransferPrice(1, a, b, "compute", "cost_plus"))
    result = game.turn()
    buyer = [e for e in result.ledger_entries if e.company_id == b and "supplied by" in e.memo]
    seller = [e for e in result.ledger_entries if e.company_id == a and "supplied to" in e.memo]
    assert len(buyer) == len(seller) == 1
    lines = {x.account: x.amount for x in buyer[0].lines}
    market = -lines[COMPUTE]
    price = lines[INTERCOMPANY_PURCHASES]
    assert market > 0 and price == round(round(market * Fraction(4, 5)) * Fraction(11, 10))
    assert {x.account: x.amount for x in seller[0].lines}[INTERCOMPANY_SALES] == -price
    types = {x.code: x.type for x in loaded.game_data.accounts}
    lines = game.consolidated(1)
    assert not any(acc in (INTERCOMPANY_SALES, INTERCOMPANY_PURCHASES) for _, acc, _ in lines)
    _assert_balanced(game, 1)
    assert fs.profit_and_loss(lines, types, 0, game.state.turn - 1).total_revenue >= 0


def test_an_unfair_price_with_minorities_raises_a_complaint(loaded: LoadedData) -> None:
    game, a, b = _two_brands(loaded)
    game.act(SellStake(1, b, 3_000))  # the buyer has outside holders
    game.act(SetTransferPrice(1, a, b, "compute", "market"))
    game.turn()
    assert not game.state.transfer_flows[0].complaint
    # "cost" is 20% under market: the minority-held buyer gains at the seller's expense
    game.act(SetTransferPrice(1, a, b, "compute", "cost"))
    months = loaded.balance.group.fairness_months
    filed = None
    for i in range(months):
        result = game.turn()
        if any(x.template == "minority_complaint_filed" for x in result.log_items):
            filed = i + 1
    assert filed == months  # within six months, on the sixth
    flow = game.state.transfer_flows[0]
    assert flow.complaint and complaint_against(game.state, b)
    assert any(q.template_id == COMPLAINT_TEMPLATE for q in game.state.queued)
    result = game.turn()
    legal = [e for e in result.ledger_entries if e.memo.startswith("Legal costs: a minority")]
    assert len(legal) == 1 and legal[0].company_id == b
    # moving to market settles it at the next month end
    event = GameEvent(
        1, 1, game.state.turn, COMPLAINT_TEMPLATE, "finance", "critical", "group", 1.0
    )
    game.state, _ = group_step(game.state, event, "correct_price")
    assert game.state.transfer_flows[0].kind == "market"
    result = game.turn()
    assert any(x.template == "minority_complaint_settled" for x in result.log_items)
    assert not complaint_against(game.state, b)
    _assert_balanced(game, 1)


def test_the_discount_shrinks_with_intra_group_supply(loaded: LoadedData) -> None:
    game, a, b = _two_brands(loaded)
    before = conglomerate(game.state, 1, game.balances, loaded.balance, loaded.game_data)
    assert before.segments == segments(game.state, 1) >= 1
    game.act(SetTransferPrice(1, a, b, "compute", "market"))
    for _ in range(3):
        game.turn()
    after = conglomerate(game.state, 1, game.balances, loaded.balance, loaded.game_data)
    assert after.intra_share > 0
    if before.discount > Fraction(1, 10):  # above the floor, synergy lowers it
        assert after.discount < before.discount
    assert after.value_cents == round(after.parts_cents * (1 - after.discount))
