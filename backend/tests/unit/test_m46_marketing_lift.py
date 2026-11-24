"""M46 (formulas 11.5): marketers direct a large budget."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tst.loader import LoadedData
from tst.sim.products import formulas as f


def test_below_the_threshold_nothing_changes(loaded: LoadedData) -> None:
    pb = loaded.balance.products
    # $200,000 a month and four marketers: the old formula exactly
    assert f.marketing_points(20_000_000, 4.0, pb) == pytest.approx(200 + 5 * 4)


def test_worked_example(loaded: LoadedData) -> None:
    pb = loaded.balance.products
    # $1.2M a month (1,200 points): two marketers lift the 1,000 above 200 by 6%
    assert f.marketing_points(120_000_000, 2.0, pb) == pytest.approx(1_200 + 10 + 1_000 * 0.06)
    # twenty marketers stop at the cap, +30%
    assert f.marketing_points(120_000_000, 20.0, pb) == pytest.approx(1_200 + 100 + 1_000 * 0.3)


@given(
    budget=st.integers(min_value=0, max_value=10**12),
    mu=st.floats(min_value=0, max_value=200, allow_nan=False),
    more=st.floats(min_value=0, max_value=50, allow_nan=False),
)
def test_lift_is_bounded_and_never_hurts(
    loaded: LoadedData, budget: int, mu: float, more: float
) -> None:
    pb = loaded.balance.products
    base = budget / pb.budget_mk_unit_cents + pb.marketer_mk * mu
    mk = f.marketing_points(budget, mu, pb)
    assert base <= mk <= base + max(0.0, budget / pb.budget_mk_unit_cents) * pb.marketer_lift_cap
    assert f.marketing_points(budget, mu + more, pb) >= mk  # more marketers never lower it
