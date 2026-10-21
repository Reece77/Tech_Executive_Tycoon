import pytest
from hypothesis import given
from hypothesis import strategies as st

from tst.sim.calendar import format_turn, turn_to_ym, ym_to_turn
from tst.sim.errors import InvalidDateError


def test_round_trip_turns_0_to_1000() -> None:
    for turn in range(1001):
        assert ym_to_turn(*turn_to_ym(turn)) == turn


@given(st.integers(min_value=-2000, max_value=5000))
def test_round_trip_property(turn: int) -> None:
    year, month = turn_to_ym(turn)
    assert 1 <= month <= 12
    assert ym_to_turn(year, month) == turn


@pytest.mark.parametrize(
    ("turn", "label"),
    [
        (0, "Jan 2010"),
        (1, "Feb 2010"),
        (2, "Mar 2010"),
        (11, "Dec 2010"),
        (12, "Jan 2011"),
        (24, "Jan 2012"),
        (359, "Dec 2039"),
        (-1, "Dec 2009"),
    ],
)
def test_format_turn(turn: int, label: str) -> None:
    assert format_turn(turn) == label


@pytest.mark.parametrize("month", [0, 13, -1])
def test_invalid_month(month: int) -> None:
    with pytest.raises(InvalidDateError):
        ym_to_turn(2010, month)
