"""M16 sub-task 4 (formulas.md 31.3): how stakes are accounted. A consolidated 80% subsidiary
shows NCI on the balance sheet and NCI's share of profit below the net result (31.8's example);
an associate grows by the group's share of its result; a stake under 20% is marked to fair
value each December, from public numbers only."""

from __future__ import annotations

from fractions import Fraction

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.finance import statements as fs
from tst.sim.finance.consolidation import Member, consolidated_lines
from tst.sim.group.models import Stake
from tst.sim.group.stakes import fair_value_cents, stakes_month
from tst.sim.ledger import (
    ASSOCIATES,
    ASSOCIATES_PROFIT,
    CASH,
    COMMON_EQUITY,
    FAIR_VALUE,
    FINANCIAL_INVESTMENTS,
    INVESTMENT_SUBSIDIARIES,
    NCI,
)
from tst.sim.mna import valuation
from tst.sim.state import with_stake

M = 1_000_000_00
REV = "4000_revenue_subscriptions"


def test_31_8_nci_through_consolidation(loaded: LoadedData) -> None:
    """The group owns 80% of a subsidiary with net assets $100M that earns $10M: NCI $20M at
    closing, $22M after the year's profit, and $2M of the profit belongs to NCI."""
    types = {a.code: a.type for a in loaded.game_data.accounts}
    sub = [(0, CASH, 100 * M), (0, COMMON_EQUITY, -100 * M), (3, CASH, 10 * M), (3, REV, -10 * M)]
    root = [
        (0, CASH, 500 * M),
        (0, COMMON_EQUITY, -500 * M),
        (1, INVESTMENT_SUBSIDIARIES, 80 * M),
        (1, CASH, -80 * M),
    ]
    member = Member(
        sub, 1, None, 1, 80 * M, -100 * M, stake_bp=8_000, effective=((1, Fraction(4, 5)),)
    )
    lines = consolidated_lines(root, [member], types)
    at_closing = fs.balance_sheet(lines, types, 1)
    assert at_closing.paid_in_equity[NCI] == 20 * M
    assert at_closing.total_assets == at_closing.total_liabilities_and_equity
    year = fs.profit_and_loss(lines, types, 0, 11)
    assert year.net_result == 10 * M and year.nci == 2 * M and year.net_to_owners == 8 * M
    end = fs.balance_sheet(lines, types, 11)
    assert end.paid_in_equity[NCI] == 22 * M
    assert end.accumulated_result == 8 * M  # the owners'
    assert end.total_assets == end.total_liabilities_and_equity == 530 * M  # 500 - 80 + 110


def _stake_state(loaded: LoadedData, stake_bp: int):  # type: ignore[no-untyped-def]
    state = fresh_game(loaded)
    target = next(c for c in state.rivals() if c.is_startup or c.rival_key[:1] == (0,))
    stake = Stake(0, 1, target.id, stake_bp, 60 * M, 60 * M, 0)
    return with_stake(state, stake), target.id


def test_an_associate_grows_by_the_groups_share_of_its_result(loaded: LoadedData) -> None:
    state, target = _stake_state(loaded, 3_000)
    state, entries = stakes_month(state, {}, {target: 20 * M}, loaded.balance, loaded.game_data)
    (entry,) = entries
    assert entry.company_id == 1
    assert {x.account: x.amount for x in entry.lines} == {
        ASSOCIATES: 6 * M,
        ASSOCIATES_PROFIT: -6 * M,
    }
    assert state.stakes[0].carrying_cents == 66 * M
    # a loss lowers it the same way
    state, entries = stakes_month(state, {}, {target: -5 * M}, loaded.balance, loaded.game_data)
    assert state.stakes[0].carrying_cents == 64_500_000_00


def test_a_small_stake_is_marked_each_december_from_public_numbers(loaded: LoadedData) -> None:
    state, target = _stake_state(loaded, 1_000)
    b, g = loaded.balance, loaded.game_data
    state, entries = stakes_month(state, {}, {target: 20 * M}, b, g)
    assert entries == () and state.stakes[0].carrying_cents == 60 * M  # not December
    from dataclasses import replace

    state = replace(state, turn=11)
    fair = fair_value_cents(state, state.stakes[0], {}, b, g)
    cap = valuation.market_cap_cents(state, target, {}, b, g)
    if cap is None:
        low, high = valuation.value_range_cents(state, target, {}, b, g)
        assert fair == round(Fraction(1, 10) * ((low + high) // 2))
    else:
        assert fair == round(Fraction(1, 10) * cap)
    state, entries = stakes_month(state, {}, {target: 20 * M}, b, g)
    (entry,) = entries
    assert {x.account: x.amount for x in entry.lines} == {
        FINANCIAL_INVESTMENTS: fair - 60 * M,
        FAIR_VALUE: -(fair - 60 * M),
    }
    assert state.stakes[0].carrying_cents == fair
