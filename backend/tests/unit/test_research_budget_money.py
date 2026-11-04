"""M12r finding 6 (Codex review 3): an AI researcher's budget is exact money (ADR-0003).

`researcher_cost_cents` turns the budget and the AI compute index into exact fractions (the
money helper from M10r finding 5), multiplies, and rounds half-to-even once (21.3).
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.finance.macro import MacroMonth
from tst.sim.research import levels
from tst.sim.research.projects import researcher_cost_cents
from tst.sim.state import GameState

AFTER_HISTORY = ym_to_turn(2027, 1)


def _at(loaded: LoadedData, index: float) -> GameState:
    turn = AFTER_HISTORY
    month = MacroMonth(turn, 4.0, 1.0, 100.0, index, 0.0)
    return replace(fresh_game(loaded), turn=turn, macro=month)


def test_half_a_cent_rounds_to_even(loaded: LoadedData) -> None:
    """600,000 cents x 0.5000075 is exactly 300,004.5, so 300,004 (the float gave 300,005)."""
    ai = levels.domain_def(loaded.game_data, "ai")
    assert ai.budget_cents == 600_000 and ai.compute_indexed
    assert 600_000 * 0.5000075 > 300_004.5  # the binary product is past the half
    assert researcher_cost_cents(_at(loaded, 0.5000075), loaded.game_data, ai) == 300_004


@settings(max_examples=300, deadline=None)
@given(
    budget=st.integers(min_value=0, max_value=10**9),
    index=st.floats(min_value=0.01, max_value=50.0, allow_nan=False, allow_infinity=False),
)
def test_matches_fraction_arithmetic(loaded: LoadedData, budget: int, index: float) -> None:
    ai = levels.domain_def(loaded.game_data, "ai").model_copy(update={"budget_cents": budget})
    expected = round(Fraction(budget) * Fraction(repr(index)))
    assert researcher_cost_cents(_at(loaded, index), loaded.game_data, ai) == expected
