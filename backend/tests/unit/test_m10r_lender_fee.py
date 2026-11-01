"""M10r finding 1 (Codex review 2, P2): a lender's fee paid before Continue is interest, below
operating profit (formulas.md 14.1, 20.3). The month's operating result that bank-loan
eligibility and the profit covenant read (CompanyState.op_history) comes from classifying the
whole month's ledger, never from the cash-flow total; burn stays separate (M8r finding 7)."""

from __future__ import annotations

from dataclasses import replace

from tests.helpers import fresh_game
from tst.balance.game import PLAYER, start_game
from tst.loader import LoadedData
from tst.sim.actions import ChooseEvent, TakeLoan
from tst.sim.decisions import Decisions
from tst.sim.finance import debt
from tst.sim.finance.statements import profit_and_loss
from tst.sim.ledger import CASH, INTEREST, LedgerEntry
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_company
from tst.sim.turn import TurnContext, snapshot_and_month_end_report

REVENUE = "4000_revenue_subscriptions"


def _month_end(
    loaded: LoadedData, revenue: int, fee: int, op_history: tuple[int, ...]
) -> GameState:
    """Codex's case: $5,000 of revenue this month and a $10,000 waiver fee answered before
    Continue (prior: cash flow -$10,000, operating 0)."""
    state = fresh_game(loaded)
    state = with_company(state, replace(state.player, op_history=op_history))
    opening = {(1, CASH): 50_000_000}
    entry = LedgerEntry.transfer(
        turn=0, company_id=1, memo="Revenue", debit=CASH, credit=REVENUE, amount=revenue
    )
    ctx = TurnContext(
        state=state,
        decisions=Decisions(),
        rng=RngFactory(1),
        balance=loaded.balance,
        data=loaded.game_data,
        opening_balances=opening,
        balances=dict(opening),
        prior_flow={1: -fee},
        prior_operating={1: 0},
    ).post(entry)
    out = snapshot_and_month_end_report(ctx)
    return out.state


def test_a_fee_paid_before_continue_is_not_operating(loaded: LoadedData) -> None:
    state = _month_end(loaded, 500_000, 1_000_000, (100_000, 100_000))
    company = state.player
    assert company.op_history[-1] == 500_000  # not 500_000 - 1_000_000
    assert company.burn_history[-1] == 500_000  # burn still counts the fee's cash (M8r)
    # Bank eligibility (every recent month profitable) and the covenant (sum positive) hold.
    stage3 = replace(company, stage=3, mrr_history=(100_000_000,))
    state = with_company(state, stage3)
    problem = debt.gate_problem(state, PLAYER, "bank_loan", loaded.balance, loaded.game_data)
    assert problem is None
    assert sum(stage3.op_history[-loaded.balance.debt.bank.covenant_profit_months :]) > 0


def test_a_waiver_answered_before_continue_then_continue(loaded: LoadedData) -> None:
    """The full path: breach, answer the lender with the waiver (choice A) before Continue,
    then Continue. The stored month equals the P&L of every line the month posted."""
    game = start_game(loaded, 3, scenario="funded_spinout")
    assert game.act(TakeLoan(game.founder_id, "venture_debt", 40_000_000))
    loan_id = game.state.company_loans(PLAYER)[0].id
    company = game.state.player
    game.state = with_company(game.state, replace(company, burn_history=(10**12,)))
    game.turn()  # the breach month: the lender event opens
    event = next(e for e in game.state.events if e.loan_id == loan_id and e.status == "open")
    before = dict(game.balances)
    month = game.state.turn
    assert game.act(ChooseEvent(game.founder_id, event.id, "A"))
    fee = game.balances.get((PLAYER, INTEREST), 0) - before.get((PLAYER, INTEREST), 0)
    assert fee > 0
    game.turn()
    lines = [
        (month, account, game.balances.get((c, account), 0) - before.get((c, account), 0))
        for (c, account) in set(game.balances) | set(before)
        if c == PLAYER
    ]
    types = {a.code: a.type for a in loaded.game_data.accounts}
    pnl = profit_and_loss(lines, types, month, month)
    assert pnl.interest >= fee
    assert game.state.player.op_history[-1] == pnl.operating_result
