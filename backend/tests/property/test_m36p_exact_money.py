"""M36p: exact money without a Fraction per call. Each integer helper in tst.sim.money gives
exactly what the rational reference gives (M36r's: Fraction(repr(rate)) arithmetic, rounded half
to even once), and the fast GameState replace builds the state dataclasses.replace builds."""

from __future__ import annotations

import dataclasses
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tst.sim.hiring.formulas import monthly_salary_cents
from tst.sim.money import (
    exact,
    exact_product,
    round_half_even,
    scaled,
    sum_times,
    times,
)
from tst.sim.state import GameState, SaveMeta, replace


def reference_exact(x: float | int) -> Fraction:
    """M36r's `exact`: the rational the number was written as."""
    return Fraction(x) if isinstance(x, int) else Fraction(repr(x))


cents = st.integers(min_value=-(10**13), max_value=10**13)
rates = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False),
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False).map(lambda v: round(v, 4)),
    st.integers(min_value=-(10**6), max_value=10**6),
    st.sampled_from([0.5, 1.5, 2.5, -0.5, 0.125, 1e-7, 1e22, 0.1, 0.3, 1 / 3]),
)


@given(rates)
def test_exact_is_the_written_rational(x: float | int) -> None:
    assert exact(x) == reference_exact(x)


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_scaled_is_numerator_over_a_power_of_ten(x: float) -> None:
    n, k = scaled(x)
    assert k >= 0
    assert Fraction(n, 10**k) == reference_exact(x)


@given(cents, rates)
def test_times_matches_the_rational_reference(amount: int, rate: float | int) -> None:
    assert times(amount, rate) == round(Fraction(amount) * reference_exact(rate))


@given(cents, rates, st.lists(rates, max_size=3))
def test_times_of_several_rates_rounds_once(
    amount: int, rate: float | int, more: list[float | int]
) -> None:
    want = Fraction(amount) * reference_exact(rate)
    for r in more:
        want *= reference_exact(r)
    assert times(amount, rate, *more) == round(want)
    assert exact_product(amount, rate, *more) == want


@given(st.floats(min_value=-1e9, max_value=1e9, allow_nan=False), rates)
def test_a_float_amount_keeps_its_binary_value(amount: float, rate: float | int) -> None:
    """M23a's `times` read a non-int amount as Fraction(amount); so does M36p's."""
    assert times(amount, rate) == round(Fraction(amount) * reference_exact(rate))


@given(st.lists(st.tuples(cents, rates), max_size=8))
def test_sum_times_is_one_rounding_of_the_exact_sum(rows: list[tuple[int, float | int]]) -> None:
    want = sum((Fraction(a) * reference_exact(r) for a, r in rows), Fraction())
    assert sum_times(rows) == round(want)
    assert sum_times(iter(rows)) == round(want)


@given(cents, st.integers(min_value=1, max_value=10**9))
def test_round_half_even_is_round_of_the_fraction(numerator: int, denominator: int) -> None:
    assert round_half_even(numerator, denominator) == round(Fraction(numerator, denominator))


@given(cents)
def test_monthly_salary_is_a_twelfth_half_even(annual: int) -> None:
    assert monthly_salary_cents(annual) == round(Fraction(annual, 12))


def test_exact_refuses_what_fraction_refused() -> None:
    for bad in (float("inf"), float("-inf"), float("nan")):
        with pytest.raises((ValueError, OverflowError)):
            exact(bad)
        with pytest.raises((ValueError, OverflowError)):
            times(100, bad)


def test_fast_state_replace_is_dataclasses_replace() -> None:
    # the fast copy skips __init__: it is exact only while GameState has no __post_init__
    assert not hasattr(GameState, "__post_init__")
    state = GameState(
        save_meta=SaveMeta(name="t", master_seed=1, scenario_id="s", difficulty="normal"),
        turn=3,
        companies=(),
    )
    state._memo["x"] = 1
    fast = replace(state, turn=4, people=())
    slow = dataclasses.replace(state, turn=4, people=())
    assert fast == slow
    assert type(fast) is GameState
    assert fast._memo == {}  # a new state remembers nothing
    assert all(
        getattr(fast, f.name) is getattr(slow, f.name)
        for f in dataclasses.fields(GameState)
        if f.init
    )
    with pytest.raises(TypeError):
        replace(state, not_a_field=1)
    with pytest.raises((TypeError, ValueError)):
        replace(state, _memo={})
