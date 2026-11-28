"""M57r-A sub-task 2 (review 10 items 7 and 8): exact money at half-cent boundaries."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from hypothesis import given
from hypothesis import strategies as st

import tst.sim.actions  # noqa: F401
from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.finserv import banks, insurance
from tst.sim.finserv.models import Bank, Insurer
from tst.sim.media.streaming import licence_month_cents
from tst.sim.money import ceil_div, times, times_over
from tst.sim.rng import RngFactory
from tst.sim.telecom.spectrum import clock, next_price

PLAYER = 1
NA = "north_america"


def test_the_clock_price_rises_in_integers() -> None:
    # Codex R10-09: a 10% step from 100 was 111 (the float 110.00000000000001 rounded up)
    assert next_price(100, 0.10) == 110
    assert next_price(50, 0.10) == 55  # Fable 13: 56 before
    assert next_price(101, 0.10) == 112  # 111.1 rounds up
    assert next_price(1, 0.05) == 2


@given(st.integers(1, 10**12), st.sampled_from([0.01, 0.05, 0.1, 0.125, 0.3, 1.0]))
def test_next_price_is_the_exact_ceiling(price: int, increment: float) -> None:
    exact = Fraction(price) * (1 + Fraction(str(increment)))
    assert next_price(price, increment) == max(1, -(-exact.numerator // exact.denominator))


def test_the_clock_compares_the_players_exact_limit() -> None:
    from tst.sim.telecom.spectrum import Bidder

    bidders = [Bidder("p", 1, 2, 110), Bidder("r", 2, 2, 109.0)]
    _, price, won = clock(bidders, 2, 100, 0.10, 10)
    assert price == 110 and won == {0: 2}


def test_times_over_rounds_once() -> None:
    # Codex R10-07: 10,000,921 cents at 500 bp a year is 41,670.5042 a month: 41,671, not the
    # 41,670 a year rounded first gives
    assert times_over(10_000_921 * 500, 12 * 10_000) == 41_671
    assert times_over(10_000_921, 12, 0.05) == 41_671
    assert times_over(6, 12) == 0 and times_over(18, 12) == 2  # half to even at .5
    assert times_over(10, 3, Fraction(1, 2)) == 2


@given(st.integers(-(10**12), 10**12), st.integers(1, 120), st.floats(0, 2, allow_nan=False))
def test_times_over_is_round_of_the_exact_quotient(amount: int, divisor: int, rate: float) -> None:
    from tst.sim.money import exact

    assert times_over(amount, divisor, rate) == round(Fraction(amount) * exact(rate) / divisor)


def test_a_fixed_rate_loan_books_one_rounded_month(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2018, 3))
    bank = Bank(
        1,
        PLAYER,
        NA,
        "chartered",
        0,
        loans=(("mortgage", 10_000_921),),
        fixed_yields=(("mortgage", 500),),
    )
    state = replace(state, finserv=replace(state.finserv, banks=(bank,)))
    _, entries, _, _ = banks.chartered_month(state, bank, RngFactory(1), b, d)
    income = next(e for e in entries if e.memo == "Bank interest income")
    assert max(x.amount for x in income.lines) == 41_671


def test_a_yearly_licence_books_exactly_its_fee() -> None:
    # Codex R10-08: 7 cents a year collected 12; 5 cents collected 0
    for fee in (7, 5, 6, 18, 1_000_007, 0):
        assert sum(licence_month_cents(fee, m) for m in range(12)) == fee
    # and every year of a longer term
    assert sum(licence_month_cents(7, m) for m in range(36)) == 21
    assert all(licence_month_cents(1_000_007, m) in (83_333, 83_334) for m in range(12))


@given(st.integers(0, 10**12), st.integers(1, 120))
def test_licence_months_sum_to_the_cumulative_entitlement(fee: int, months: int) -> None:
    total = sum(licence_month_cents(fee, m) for m in range(months))
    assert total == round(Fraction(fee * months, 12))


def test_a_claims_reserve_clears_when_claims_stop(loaded: LoadedData) -> None:
    """Codex R10-07: a 1-cent property reserve survived for ever (1 / 9 rounds to 0)."""
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2018, 3))
    insurer = Insurer(
        1,
        PLAYER,
        investments_cents=10**9,
        reserves_cents=1_000_001,
        reserves_by_line=(("property", 1_000_000), ("life", 1)),
    )
    months = 0
    while insurer.reserves_cents > 0 and months < 1000:
        insurer, entries, _, _ = insurance.insurer_month(state, insurer, b, d)
        assert all(sum(x.amount for x in e.lines) == 0 for e in entries)
        months += 1
    assert insurer.reserves_cents == 0
    assert all(v == 0 for _, v in insurer.reserves_by_line)
    assert months < 300


def test_ceil_div() -> None:
    assert ceil_div(1, 9) == 1 and ceil_div(9, 9) == 1 and ceil_div(10, 9) == 2


def test_a_custom_rivals_cash_rounds_half_even() -> None:
    assert times(5, 0.5) == 2 and times(7, 0.5) == 4  # round() on the float gave the same
    assert times(3, 1.5) == 4 and times(1, 2.5) == 2
