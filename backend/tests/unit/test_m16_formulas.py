"""M16 sub-task 2 (formulas.md 31.3-31.8): the group's formulas and the 31.8 worked examples,
exact in integer cents."""

from __future__ import annotations

from fractions import Fraction

from tst.loader import LoadedData
from tst.sim.group import formulas as gf

M = 1_000_000_00  # $1M in cents
B = 1_000 * M


def test_31_8_consolidation_with_nci(loaded: LoadedData) -> None:
    """80% of a subsidiary with net assets $100M and profit $10M: NCI $20M and $2M."""
    assert gf.treatment(8_000, loaded.balance) == "consolidated"
    assert gf.nci_cents(100 * M, 8_000) == 20 * M
    assert gf.nci_cents(10 * M, 8_000) == 2 * M


def test_31_8_equity_method(loaded: LoadedData) -> None:
    """30% bought for $60M in a company earning $20M and paying $5M: $64.5M."""
    assert gf.treatment(3_000, loaded.balance) == "equity"
    assert gf.equity_method_cents(60 * M, 20 * M, 5 * M, 3_000) == 64_500_000_00


def test_31_8_conglomerate_discount(loaded: LoadedData) -> None:
    """$40B of parts in 4 unrelated segments with 10% intra-group revenue: d 0.175, $33.0B."""
    d = gf.conglomerate_discount(4, 0.10, loaded.balance)
    assert d == Fraction(175, 1000)
    assert gf.discounted_cents(40 * B, d) == 33 * B


def test_the_discount_is_clamped(loaded: LoadedData) -> None:
    assert gf.conglomerate_discount(1, 0.5, loaded.balance) == Fraction(1, 10)  # floor 10%
    assert gf.conglomerate_discount(12, 0.0, loaded.balance) == Fraction(1, 4)  # cap 25%


def test_treatment_lines(loaded: LoadedData) -> None:
    b = loaded.balance
    assert [gf.treatment(x, b) for x in (10_000, 5_000, 4_999, 2_000, 1_999, 0)] == [
        "consolidated",
        "consolidated",
        "equity",
        "equity",
        "fair_value",
        "fair_value",
    ]


def test_stake_prices(loaded: LoadedData) -> None:
    g = loaded.balance.group
    # 25% of an unlisted $200M subsidiary sells at 20% below value: $40M
    assert gf.stake_price_cents(200 * M, 2_500, g.private_discount) == 40 * M
    # buying out 20% minorities of a $100M company at 25% over value: $25M
    assert gf.buyout_cents(100 * M, 2_000, g.buyout_premium) == 25 * M
    # 0 -> 10% of a $1B listed rival: midpoint 5% x 0.5% a point = +2.5%
    assert gf.market_stake_cents(B, 0, 1_000, g.stake_impact) == 102_500_000_00
    # later percentages cost more than earlier ones
    assert gf.market_stake_cents(B, 1_000, 2_000, g.stake_impact) > gf.market_stake_cents(
        B, 0, 1_000, g.stake_impact
    )


def test_minority_seats(loaded: LoadedData) -> None:
    b = loaded.balance
    assert [gf.minority_seats(x, b) for x in (0, 1_499, 1_500, 2_999, 3_000, 4_900)] == [
        0,
        0,
        1,
        1,
        2,
        3,
    ]


def test_transfer_prices_and_fairness(loaded: LoadedData) -> None:
    b = loaded.balance
    assert gf.transfer_price_cents("cost", 800, 1_000, b) == 800
    assert gf.transfer_price_cents("cost_plus", 800, 1_000, b) == 880  # 10% margin
    assert gf.transfer_price_cents("market", 800, 1_000, b) == 1_000
    assert gf.unfair(800, 1_000, b)  # 20% below market
    assert not gf.unfair(900, 1_000, b)  # exactly the 10% band
    assert gf.unfair(1_101, 1_000, b)
