"""The closing function (ADR-0018 section 3, formulas.md 14.5): after a close the unallocated
pool is the target share of post-money FD (within one share), the new investor owns
amount / V_post (within one share), SAFE holders own f of the pre-money FD (within one
share), and the shares add up."""

from __future__ import annotations

from fractions import Fraction

from hypothesis import assume, given
from hypothesis import strategies as st

from tst.sim.finance import formulas as f

TARGET = Fraction(1, 10)


@given(
    fd=st.integers(min_value=1_000_000, max_value=200_000_000),
    pool_share=st.fractions(min_value=0, max_value=Fraction(1, 5)),
    safe_frac=st.fractions(min_value=0, max_value=Fraction(2, 5), max_denominator=1000),
    pre=st.integers(min_value=100_000_000, max_value=50_000_000_000),
    amount_share=st.fractions(min_value=Fraction(1, 100), max_value=Fraction(1, 2)),
)
def test_close_hits_its_targets(
    fd: int, pool_share: Fraction, safe_frac: Fraction, pre: int, amount_share: Fraction
) -> None:
    unallocated = int(fd * pool_share)
    amount = int(pre * amount_share)
    assume(amount > 0)
    c = f.close_round(fd, safe_frac, unallocated, pre, amount, TARGET)
    after = c.fd_after
    assert after == fd + c.pool_shares + c.safe_shares + c.new_shares
    post = pre + amount
    # The new investor: amount / V_post of the company, within one share.
    assert abs(c.new_shares - Fraction(amount, post) * after) <= 1
    # SAFE holders: f of the company just before the new money, within one share.
    assert abs(c.safe_shares - safe_frac * c.fd_pre) <= 1
    if c.pool_shares > 0:  # topped up: exactly the target, within one share
        assert abs(unallocated + c.pool_shares - TARGET * after) <= 1
    else:  # already at or above the target
        assert unallocated >= TARGET * after - 1
