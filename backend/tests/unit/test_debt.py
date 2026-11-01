"""Debt (docs/formulas.md 20.3, M10 sub-task 4): signing, warrants, the monthly schedule,
early repayment, covenants, the lender event and a called loan."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tst.balance.game import PLAYER, Game, start_game
from tst.loader import LoadedData
from tst.sim.actions import ChooseEvent, RepayLoan, TakeLoan
from tst.sim.finance import debt
from tst.sim.finance.captable import fd_shares
from tst.sim.ledger import CASH, DEBT, INTEREST
from tst.sim.state import with_company


def _game(loaded: LoadedData, seed: int = 3) -> Game:
    return start_game(loaded, seed, scenario="funded_spinout")


def _ledger_ok(game: Game) -> None:
    assert sum(game.balances.values()) == 0  # every entry balances (ADR-0003)


def test_venture_debt_after_the_seed_signs_with_warrants(loaded: LoadedData) -> None:
    game = _game(loaded)
    t = debt.terms(game.state, PLAYER, "venture_debt", loaded.balance, loaded.game_data)
    assert t.problem is None and t.lender is not None and t.lender.key == "svb"
    assert t.max_cents == 150_000_000 * 3000 // 10_000  # 30% of the $1.5M seed
    assert t.rate_bp == round(0.11 * 100) + 600  # January 2010: 0.11% + 6%
    fd = fd_shares(game.state, PLAYER)
    cash = game.cash
    assert game.act(TakeLoan(game.founder_id, "venture_debt", t.max_cents))
    loan = game.state.company_loans(PLAYER)[0]
    assert game.cash == cash + t.max_cents
    assert game.balances[(PLAYER, DEBT)] == -t.max_cents
    after = fd_shares(game.state, PLAYER)
    assert after - fd == loan.warrant_shares
    assert loan.warrant_shares / after == pytest.approx(0.0025, abs=1e-7)
    assert not game.act(TakeLoan(game.founder_id, "venture_debt", 10_000_000))  # used up
    _ledger_ok(game)


def test_schedule_interest_then_equal_principal_to_zero(loaded: LoadedData) -> None:
    game = _game(loaded)
    amount = 45_000_000
    assert game.act(TakeLoan(game.founder_id, "venture_debt", amount))
    loan = game.state.company_loans(PLAYER)[0]
    plan = debt.schedule(loan, loan.signed_turn)
    assert len(plan) == 36
    assert all(p.principal_cents == 0 for p in plan[:12])
    assert sum(p.principal_cents for p in plan) == amount
    assert plan[-1].balance_after_cents == 0
    interest = 0
    for _ in range(36):
        before = game.balances.get((PLAYER, INTEREST), 0)
        game.turn()
        interest += game.balances.get((PLAYER, INTEREST), 0) - before
        _ledger_ok(game)
        if game.state.ended:
            pytest.skip("this seed went bankrupt first")
    loan = game.state.loan(loan.id)
    assert loan is not None and loan.status == "repaid"
    assert loan.principal_paid_cents == amount
    assert game.balances.get((PLAYER, DEBT), 0) == 0
    assert loan.interest_paid_cents == interest > 0


def test_early_repayment(loaded: LoadedData) -> None:
    game = _game(loaded)
    assert game.act(TakeLoan(game.founder_id, "venture_debt", 40_000_000))
    loan_id = game.state.company_loans(PLAYER)[0].id
    assert not game.act(RepayLoan(game.founder_id, loan_id, 50_000_000))  # above the balance
    assert game.act(RepayLoan(game.founder_id, loan_id, 10_000_000))
    loan = game.state.loan(loan_id)
    assert loan is not None and loan.balance_cents == 30_000_000 and loan.active
    assert game.act(RepayLoan(game.founder_id, loan_id))
    loan = game.state.loan(loan_id)
    assert loan is not None and loan.status == "repaid" and loan.balance_cents == 0
    _ledger_ok(game)


def test_bank_loan_needs_stage_3_and_profits(loaded: LoadedData) -> None:
    game = _game(loaded)
    problem = debt.gate_problem(game.state, PLAYER, "bank_loan", loaded.balance, loaded.game_data)
    assert problem is not None and "stage 3" in problem
    company = replace(
        game.state.company(PLAYER), stage=3, op_history=(5, 5, 5), mrr_history=(1_000_000_00,)
    )
    game.state = with_company(game.state, company)
    t = debt.terms(game.state, PLAYER, "bank_loan", loaded.balance, loaded.game_data)
    assert t.problem is None and t.max_cents == 12 * 1_000_000_00
    assert t.rate_bp == 11 + 300 and t.term_months == 48 and t.warrant_bp == 0
    game.state = with_company(game.state, replace(company, op_history=(5, -1, 5)))
    assert debt.gate_problem(game.state, PLAYER, "bank_loan", loaded.balance, loaded.game_data)


def _breach(game: Game) -> None:
    """Make last month's burn far larger than cash covers."""
    company = game.state.company(PLAYER)
    game.state = with_company(game.state, replace(company, burn_history=(10**12,)))


def test_breach_queues_the_lender_event_and_its_choices_apply(loaded: LoadedData) -> None:
    game = _game(loaded)
    assert game.act(TakeLoan(game.founder_id, "venture_debt", 40_000_000))
    loan_id = game.state.company_loans(PLAYER)[0].id
    game.turn()  # the first month end records a modest burn: no breach
    assert game.state.loan(loan_id).breach_turn is None  # type: ignore[union-attr]
    _breach(game)
    original = game.state.loan(loan_id).balance_cents  # type: ignore[union-attr]
    turn = game.state.turn
    game.turn()
    loan = game.state.loan(loan_id)
    assert loan is not None and loan.breach_turn == turn and loan.breaches == 1
    events = [e for e in game.state.events if e.loan_id == loan_id]
    assert len(events) == 1 and events[0].severity == "critical"
    event = events[0]
    assert event.template_id == debt.BREACH_TEMPLATE and event.status == "open"
    assert [c.key for c in event.choices] == ["A", "B", "C"]
    # Choice C repays a quarter of the balance now.
    balance_now = loan.balance_cents
    assert balance_now == original
    assert game.act(ChooseEvent(game.founder_id, event.id, "C"))
    loan = game.state.loan(loan_id)
    assert loan is not None and loan.balance_cents == balance_now - balance_now // 4
    _ledger_ok(game)


def test_rate_and_fee_choices(loaded: LoadedData) -> None:
    for key in ("A", "B"):
        game = _game(loaded)
        assert game.act(TakeLoan(game.founder_id, "venture_debt", 40_000_000))
        loan_id = game.state.company_loans(PLAYER)[0].id
        _breach(game)
        game.turn()
        event = next(e for e in game.state.events if e.loan_id == loan_id)
        loan = game.state.loan(loan_id)
        assert loan is not None
        interest = game.balances.get((PLAYER, INTEREST), 0)
        assert game.act(ChooseEvent(game.founder_id, event.id, key))
        after = game.state.loan(loan_id)
        assert after is not None
        if key == "A":
            fee = game.balances.get((PLAYER, INTEREST), 0) - interest
            assert 0 < fee <= loan.balance_cents // 100
            assert after.rate_bp == loan.rate_bp
        else:
            assert after.rate_bp == loan.rate_bp + 200
        _ledger_ok(game)


def test_cure_then_second_breach_calls_the_loan(loaded: LoadedData) -> None:
    game = _game(loaded)
    assert game.act(TakeLoan(game.founder_id, "venture_debt", 40_000_000))
    loan_id = game.state.company_loans(PLAYER)[0].id
    _breach(game)
    game.turn()
    first = game.state.loan(loan_id).breach_turn  # type: ignore[union-attr]
    cure = loaded.balance.debt.breach.cure_months
    for _ in range(cure + 1):
        _breach(game)
        game.turn()  # Game answers the critical event with its first choice
    loan = game.state.loan(loan_id)
    assert loan is not None and loan.status == "called" and loan.balance_cents == 0
    assert game.state.turn - 1 - (first or 0) <= loaded.balance.debt.breach.call_window_months
    assert game.balances.get((PLAYER, DEBT), 0) == 0
    assert any(e.template_id == debt.CALLED_TEMPLATE for e in game.state.events)
    _ledger_ok(game)
    assert game.balances[(PLAYER, CASH)] == game.cash
