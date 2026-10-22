import pytest

from tst.sim.errors import InvalidMoneyError
from tst.sim.money import cents, pct_of


@pytest.mark.parametrize(
    ("dollars", "expected"),
    [
        (0, 0),
        (50_000, 5_000_000),
        (-3, -300),
        ("0", 0),
        ("12", 1200),
        ("12.5", 1250),
        ("12.05", 1205),
        ("1,234.56", 123_456),
        ("$50,000", 5_000_000),
        ("-$7.10", -710),
        ("  42.00 ", 4200),
    ],
)
def test_cents(dollars: str | int, expected: int) -> None:
    assert cents(dollars) == expected


@pytest.mark.parametrize("bad", ["", "abc", "1.234", "1,23", "12.", "1e3", "$-5", True, 1.5])
def test_cents_rejects_bad_input(bad: object) -> None:
    with pytest.raises(InvalidMoneyError):
        cents(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("amount", "bp", "expected"),
    [
        (10_000, 2000, 2000),  # 20%
        (958_333, 2000, 191_667),  # formulas.md section 8 worked example
        (5_000_000, 10_000, 5_000_000),
        (5_000_000, 15_000, 7_500_000),
        (5_000_000, 6000, 3_000_000),
        (1, 5000, 0),  # 0.5 -> 0 (round half to even)
        (3, 5000, 2),  # 1.5 -> 2
        (5, 5000, 2),  # 2.5 -> 2
        (7, 5000, 4),  # 3.5 -> 4
        (1, 5001, 1),  # just above half rounds up
        (1, 4999, 0),
        (-1, 5000, 0),  # -0.5 -> 0
        (-3, 5000, -2),  # -1.5 -> -2
        (-5, 5000, -2),  # -2.5 -> -2
        (0, 1234, 0),
    ],
)
def test_pct_of_rounds_half_to_even(amount: int, bp: int, expected: int) -> None:
    assert pct_of(amount, bp) == expected
