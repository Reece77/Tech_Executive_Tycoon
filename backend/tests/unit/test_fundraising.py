"""Fundraising through actions and turns (formulas.md 14.3-14.5, ADR-0018): V_base, SAFE
answers and their money, term sheets from investor firms, accepting one, and the close in
phase 1 with the pool top-up, SAFE conversion, new preferred, fees and a board seat."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from tests.helpers import fresh_game
from tests.unit.test_hiring_phases import Game
from tst.loader import LoadedData
from tst.sim.actions import AcceptTermSheet, RaiseSafe, StartRound
from tst.sim.errors import FinanceRuleError, GameOverError, UnknownTermSheetError
from tst.sim.finance import fundraising as fr
from tst.sim.finance.captable import fd_shares, person_shares, share_price, unallocated
from tst.sim.ledger import CASH, account_balance
from tst.sim.state import GameState, with_company

FOUNDER = 1
GARAGE_CASH = 5_000_000


def garage(loaded: LoadedData, seed: int = 16) -> Game:  # several firms answer its seed
    return Game(loaded, fresh_game(loaded, seed=seed, scenario="garage_bootstrap"), GARAGE_CASH)


def with_mrr(state: GameState, history: tuple[int, ...]) -> GameState:
    return with_company(state, replace(state.player, mrr_history=history))


def test_base_value_from_state(loaded: LoadedData) -> None:
    state = fresh_game(loaded, scenario="garage_bootstrap")
    assert fr.base_value(state, 1, loaded.balance, loaded.game_data) == 210_000_000  # floor
    growing = with_mrr(state, (0, 0, 0, 0, 0, 100_000, 1_000_000))
    assert fr.company_growth(growing, 1, loaded.balance) == 3  # MRR six months ago was 0
    assert fr.arr_cents(growing, 1, loaded.balance) == 12_000_000
    assert fr.climate(state, loaded.game_data) == 0.9  # 2010


def test_safe_rules(loaded: LoadedData) -> None:
    game = garage(loaded)
    with pytest.raises(FinanceRuleError, match=r"\$25,000 to \$2,000,000"):
        game.act(RaiseSafe(FOUNDER, 2_000_000, 100_000_000))
    with pytest.raises(FinanceRuleError, match="cap is too low"):
        game.act(RaiseSafe(FOUNDER, 50_000_000, 60_000_000))  # would claim 83%
    game.act(RaiseSafe(FOUNDER, 30_000_000, 100_000_000))
    assert game.state.person_state(FOUNDER).energy == 90
    with pytest.raises(FinanceRuleError, match="already open"):
        game.act(RaiseSafe(FOUNDER, 30_000_000, 100_000_000))


def test_a_low_cap_fills_and_a_high_cap_does_not(loaded: LoadedData) -> None:
    game = garage(loaded)
    game.act(RaiseSafe(FOUNDER, 30_000_000, 100_000_000))  # 1.2 x $2.1M / $1M: p ~ 1
    result = game.turn()
    (safe,) = game.state.safes
    assert (safe.status, safe.resolved_turn) == ("outstanding", 0)
    assert account_balance(game.balances, 1, "2600_safes") == -30_000_000
    assert account_balance(game.balances, 1, CASH) < GARAGE_CASH + 30_000_000  # less the fee
    assert any(i.template == "safe_filled" for i in result.log_items)
    game.act(RaiseSafe(FOUNDER, 30_000_000, 5_000_000_000))  # a $50M cap: p ~ 0
    result = game.turn()
    assert game.state.safes[1].status == "declined"
    assert any(i.template == "safe_declined" for i in result.log_items)


def first_sheets(loaded: LoadedData, game: Game, series: str, target: int) -> None:
    game.act(StartRound(FOUNDER, series, target))
    result = game.turn()
    (rnd,) = [r for r in game.state.rounds if r.status in ("open", "failed")]
    assert rnd.status == "open", "this seed should bring term sheets"
    assert any(i.template == "term_sheets_arrived" for i in result.log_items)


def test_seed_round_closes_with_the_14_5_math(loaded: LoadedData) -> None:
    game = garage(loaded)
    game.act(RaiseSafe(FOUNDER, 30_000_000, 100_000_000))
    game.turn()
    with pytest.raises(FinanceRuleError, match="next round is the Seed"):
        game.act(StartRound(FOUNDER, "a", 500_000_000))
    first_sheets(loaded, game, "seed", 150_000_000)
    sheets = [t for t in game.state.term_sheets if t.status == "offered"]
    firms = {f.key for f in loaded.game_data.investors if "seed" in f.series}
    assert sheets and {t.firm for t in sheets} <= firms
    best = max(sheets, key=lambda t: t.pre_money_cents)
    plan = fr.plan_close(game.state, 1, best.pre_money_cents, best.amount_cents, loaded.balance)
    cash_before = account_balance(game.balances, 1, CASH)
    game.act(AcceptTermSheet(FOUNDER, best.id))
    assert {t.status for t in game.state.term_sheets if t.id != best.id} <= {"lapsed"}
    with pytest.raises(FinanceRuleError, match="already open"):
        game.act(StartRound(FOUNDER, "seed", 100_000_000))
    result = game.turn()

    state = game.state
    (rnd,) = [r for r in state.rounds if r.status == "closed"]
    assert (rnd.lead_firm, rnd.closed_turn, rnd.down_round) == (best.firm, 2, False)
    c = plan.closing
    assert (rnd.pool_shares, rnd.safe_shares, rnd.new_shares) == (
        c.pool_shares,
        c.safe_shares,
        c.new_shares,
    )
    fd = fd_shares(state, 1)
    assert fd == c.fd_after  # the preview matches the cap table after closing
    post = best.pre_money_cents + best.amount_cents
    assert abs(unallocated(state, 1) - fd / 10) <= 1
    investor = next(e for e in state.cap_entries if e.firm == best.firm)
    assert abs(investor.shares - fd * best.amount_cents / post) <= 1
    holders = next(e for e in state.cap_entries if e.share_class == "safe_conversion")
    assert abs(holders.shares - Fraction(30_000_000, 100_000_000) * c.fd_pre) <= 1
    assert state.safes[0].status == "converted" and state.safes[0].converted_round_id == rnd.id
    assert share_price(state, 1) == c.price
    assert person_shares(state, 1, FOUNDER) == 9_000_000
    # Money: the round in, the SAFE converted, legal fees out.
    assert account_balance(game.balances, 1, "2600_safes") == 0
    assert account_balance(game.balances, 1, "3100_preferred_equity") == -(
        best.amount_cents + 30_000_000
    )
    assert account_balance(game.balances, 1, CASH) > cash_before + best.amount_cents - 10_000_000
    # The board forms in phase 1 (the founder and the lead's director at 70), then phase 10
    # moves it one month toward T = 50 + 0 (no revenue yet) + 10 (a long runway) = 60.
    assert [(s.kind, s.firm, s.confidence) for s in state.board(1)] == [
        ("common", None, None),
        ("investor", best.firm, pytest.approx(68)),
    ]
    assert any(i.template == "round_closed" for i in result.log_items)
    with pytest.raises(FinanceRuleError, match="needs ARR of at least"):
        game.act(StartRound(FOUNDER, "a", 500_000_000))


def test_an_unaccepted_round_lapses(loaded: LoadedData) -> None:
    game = garage(loaded)
    first_sheets(loaded, game, "seed", 150_000_000)
    sheet = next(t for t in game.state.term_sheets if t.status == "offered")
    game.turn()  # turn 1: still open
    result = game.turn()  # turn 2: its last turn passes
    assert game.state.rounds[0].status == "lapsed"
    assert all(t.status == "lapsed" for t in game.state.term_sheets)
    assert any(i.template == "round_lapsed" for i in result.log_items)
    with pytest.raises(FinanceRuleError, match="no longer open"):
        game.act(AcceptTermSheet(FOUNDER, sheet.id))
    with pytest.raises(UnknownTermSheetError):
        game.act(AcceptTermSheet(FOUNDER, 999))


def test_term_sheets_are_seeded(loaded: LoadedData) -> None:
    runs = []
    for _ in range(2):
        game = garage(loaded, seed=8)
        game.act(StartRound(FOUNDER, "seed", 150_000_000))
        game.turn()
        runs.append([(t.firm, t.pre_money_cents, t.amount_cents) for t in game.state.term_sheets])
    assert runs[0] == runs[1]


def test_an_ended_game_refuses_actions(loaded: LoadedData) -> None:
    game = garage(loaded)
    game.state = replace(
        game.state, save_meta=replace(game.state.save_meta, game_state="bankrupt", ended_turn=0)
    )
    with pytest.raises(GameOverError, match="bankrupt"):
        game.act(RaiseSafe(FOUNDER, 30_000_000, 100_000_000))
    with pytest.raises(GameOverError):
        game.turn()


def test_a_down_round_costs_the_board_15_points(loaded: LoadedData) -> None:
    from tests.helpers import move_directors
    from tst.sim.finance.models import FundingRound, TermSheet
    from tst.sim.rng import RngFactory
    from tst.sim.state import with_round, with_term_sheet

    state = move_directors(fresh_game(loaded, scenario="funded_spinout"))  # $0.75 seed
    assert [s.confidence for s in state.board(1)] == [None, 70]
    state = with_round(state, FundingRound(2, 1, "a", "accepted", 300_000_000, 0, 2, 1))
    state = with_term_sheet(
        state, TermSheet(1, 2, "accel", 400_000_000, 300_000_000, "accepted", 0, 2)
    )
    state = replace(state, next_ids=replace(state.next_ids, round=3, term_sheet=2))
    state, _, _ = fr.close_rounds(state, RngFactory(1), loaded.balance, loaded.game_data)
    rnd = state.funding_round(2)
    assert rnd is not None and rnd.down_round and rnd.price is not None and rnd.price < 75
    seats = state.board(1)
    assert [s.kind for s in seats] == ["common", "investor", "common", "investor"]
    assert [s.confidence for s in seats] == [None, 55, None, 70]  # new directors start at 70
    assert seats[3].firm == "accel"
