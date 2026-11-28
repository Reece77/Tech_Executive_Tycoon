"""M60: `tst.sim.compound.compounded` returns exactly the float of the month-by-month loop it
replaced (media growth, ad spend), for any start, month, rates and order of calls."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tst.sim import compound
from tst.sim.compound import compounded, compounded_slow

RATES = st.lists(st.floats(-0.2, 0.5, allow_nan=False), min_size=1, max_size=80)


def test_before_the_start_it_is_the_initial_value() -> None:
    assert compounded(3.5, 192, 150, lambda y: 0.1, "t") == 3.5


def test_a_rate_drawn_later_never_reuses_the_old_value() -> None:
    """January before the year's draw reads the fallback; after it, the drawn rate."""
    rates = {2026: 0.05}
    before = compounded(1.0, 192, 204, lambda y: rates.get(y, 0.01), "late")
    rates[2027] = 0.3
    after = compounded(1.0, 192, 204, lambda y: rates.get(y, 0.01), "late")
    assert before == compounded_slow(1.0, 192, 204, lambda y: 0.05 if y == 2026 else 0.01)
    assert after == compounded_slow(1.0, 192, 204, lambda y: rates.get(y, 0.01))
    assert before != after


@settings(max_examples=150, deadline=None)
@given(
    rates=RATES,
    start=st.integers(-24, 400),
    months=st.lists(st.integers(0, 960), min_size=1, max_size=6),
    initial=st.floats(0.001, 1e9, allow_nan=False),
)
def test_the_same_float_as_month_by_month(
    rates: list[float], start: int, months: list[int], initial: float
) -> None:
    compound._KEPT.clear()
    first = start // 12 + 2010

    def rate(year: int) -> float:
        return rates[(year - first) % len(rates)]

    for m in months:  # any order of calls, the memo kept between them
        turn = start + m
        assert compounded(initial, start, turn, rate, "p") == compounded_slow(
            initial, start, turn, rate
        )
