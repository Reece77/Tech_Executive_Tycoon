"""The board (formulas.md 14.6): seats per round, monthly confidence toward its target,
quarterly meetings and warnings, and the removal vote, which needs a majority of all seats so
it can only succeed after Series B."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, make_person, move_directors, with_employee
from tst.loader import LoadedData
from tst.sim.data_models import Series
from tst.sim.finance import formulas as f
from tst.sim.finance.board import (
    actual_growth,
    average_confidence,
    board_month,
    growth_term,
    next_meeting_turn,
    seat_board,
)
from tst.sim.finance.models import FundingRound
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_company, with_round

FLAT_MRR = (1_000_000,) * 13  # $10,000 a month, not growing


def board_after(loaded: LoadedData, series: Series) -> GameState:
    """A funded spinout whose last priced round is `series`, with that round's board."""
    state = move_directors(fresh_game(loaded, scenario="funded_spinout"))
    for i, s in enumerate(("a", "b")[: ("seed", "a", "b").index(series)], start=2):
        state = with_round(
            state,
            FundingRound(
                i, 1, s, "closed", 1, 0, 0, closed_turn=0, lead_firm="accel",
                pre_money_cents=1_000_000_000, amount_cents=1, fd_pre=10_000_000,
            ),
        )  # fmt: skip
        state = replace(state, next_ids=replace(state.next_ids, round=i + 1))
        state = seat_board(state, 1, s, "accel", i, RngFactory(1), loaded.balance, loaded.game_data)
    return with_company(state, replace(state.player, mrr_history=FLAT_MRR))


def months(loaded: LoadedData, state: GameState, n: int, cash: int) -> tuple[GameState, list[str]]:
    templates: list[str] = []
    for _ in range(n):
        state, logs = board_month(state, {1: cash}, loaded.balance, loaded.game_data)
        templates += [i.template or "" for i in logs]
        if state.ended:
            break
        state = replace(state, turn=state.turn + 1)
    return state, templates


def test_seats_after_each_round(loaded: LoadedData) -> None:
    kinds = {
        series: sorted(s.kind for s in board_after(loaded, series).board(1))
        for series in ("seed", "a", "b")
    }
    assert kinds == {
        "seed": ["common", "investor"],
        "a": ["common", "common", "investor", "investor"],
        "b": ["common", "common", "independent", "investor", "investor", "investor"],
    }
    seats = board_after(loaded, "b").board(1)
    assert seats[0].person_id == 1  # the founder holds the first common seat
    directors = {s.person_id for s in seats[1:]}
    assert len(directors) == 5 and 1 not in directors


def test_confidence_follows_its_target(loaded: LoadedData) -> None:
    bb = loaded.balance.board
    state = board_after(loaded, "seed")
    # Flat MRR against an expected 200% a year: growth -20; a big cash pile: runway +10;
    # First Round's patience +5. T = 45.
    assert growth_term(state, 1, loaded.balance) == -20
    after, _ = months(loaded, state, 1, 10**12)
    expected = f.next_confidence(bb.start, 45, bb)
    assert after.board(1)[1].confidence == pytest.approx(expected)
    assert average_confidence(after, 1) == pytest.approx(expected)


def test_quarterly_meetings_and_warnings(loaded: LoadedData) -> None:
    state = replace(board_after(loaded, "seed"), turn=0)  # January 2010
    _, templates = months(loaded, state, 12, 0)  # broke: runway under 3 months
    assert templates.count("board_meeting") == 4  # March, June, September, December
    assert "board_warning" in templates
    assert templates.index("board_meeting") == 0  # the first meeting is at March's end


def test_no_product_penalty_while_revenue_history_is_short(loaded: LoadedData) -> None:
    state = board_after(loaded, "seed")
    young = with_company(state, replace(state.player, mrr_history=()))
    assert growth_term(young, 1, loaded.balance) == 0
    later = replace(young, turn=12)
    assert growth_term(later, 1, loaded.balance) == loaded.balance.board.no_product_penalty


def collapse(loaded: LoadedData, series: Series) -> tuple[GameState, list[str]]:
    """No growth and no cash: T = 50 - 20 - 30 + patience, so investors fall below 25."""
    state = board_after(loaded, series)
    staff = make_person(loaded, 2)
    state = with_employee(loaded, state, staff, 20_000_000)  # costs, so the runway is short
    return months(loaded, state, 24, 0)


def test_a_collapse_after_series_b_removes_the_founder(loaded: LoadedData) -> None:
    state, templates = collapse(loaded, "b")
    assert (state.save_meta.game_state, state.ended) == ("founder_removed", True)
    assert state.save_meta.ended_turn == state.turn
    assert templates[-1] == "founder_removed"
    seats = state.board(1)
    votes = [s for s in seats if s.votes and s.months_below >= 3]
    assert 2 * len(votes) > len(seats)


def test_the_same_collapse_after_series_a_does_not(loaded: LoadedData) -> None:
    state, templates = collapse(loaded, "a")
    assert not state.ended and "founder_removed" not in templates
    seats = state.board(1)
    assert all(s.months_below >= 3 for s in seats if s.votes)  # both investors vote: a tie


def test_each_director_keeps_six_month_ends_of_confidence(loaded: LoadedData) -> None:
    """M4b: the Board tab's trend; the oldest value drops off after history_months."""
    state, _ = months(loaded, board_after(loaded, "seed"), 8, 10**12)
    seat = state.board(1)[1]
    assert len(seat.history) == loaded.balance.board.history_months == 6
    assert seat.history[-1] == seat.confidence
    assert list(seat.history) == sorted(seat.history, reverse=True)  # falling toward 45


def test_next_meeting_and_actual_growth(loaded: LoadedData) -> None:
    bb = loaded.balance.board
    assert [next_meeting_turn(t, bb) for t in (0, 2, 3, 11)] == [2, 2, 5, 11]
    state = board_after(loaded, "seed")
    assert actual_growth(state, 1, loaded.balance) == 0.0  # flat MRR
    young = with_company(state, replace(state.player, mrr_history=(5, 6)))
    assert actual_growth(young, 1, loaded.balance) is None  # under 6 months of revenue
