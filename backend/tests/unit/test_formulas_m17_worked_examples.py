"""docs/formulas.md 33.3 and 33.5 worked examples (M17 sub-task 1), as unit tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tst.balance.game import start_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.commodities import offtake, power


def test_33_3_lithium_offtake_collar(loaded: LoadedData) -> None:
    """Signed January 2020 at $8,000/t for 5 years: the collar is $6,000-$10,000. In 2022
    (spot $63,700) the company pays $10,000; in 2025 (spot $9,000) it pays $9,000."""
    b, d = loaded.balance, loaded.game_data
    state = replace(start_game(loaded, 1).state, turn=ym_to_turn(2020, 1))
    q = offtake.offtake_quote(state, "lithium_carbonate", "sqm", 5, 100.0, 0.0, b, d)
    assert q.price == pytest.approx(8000)
    assert (q.floor, q.ceiling) == (pytest.approx(6000), pytest.approx(10000))
    assert q.months == 60
    deal = offtake.deal_from_quote(state, 1, 1, q)
    assert deal.end_turn == ym_to_turn(2024, 12)
    assert deal.price_for(63_700) == pytest.approx(10_000)
    assert deal.price_for(9_000) == pytest.approx(9_000)
    assert deal.price_for(5_000) == pytest.approx(6_000)  # the floor binds too


def test_33_5_regional_power() -> None:
    """A GPU data centre's $200 a CU-month power costs $170 in South and Southeast Asia
    (index 0.85) and $300 at the example's Europe index of 1.5."""
    assert power.opex_cents(20_000, 0.85) == pytest.approx(17_000)
    assert power.opex_cents(20_000, 1.5) == pytest.approx(30_000)


def test_33_5_power_index_by_region(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(start_game(loaded, 1).state, turn=ym_to_turn(2023, 6))
    assert power.kind_index(state, "data_centre_gpu", "north_america", b, d) == 1.0
    ssea = power.kind_index(state, "data_centre_gpu", "south_southeast_asia", b, d)
    assert ssea == pytest.approx(0.85)
    assert power.opex_cents(20_000, ssea) == pytest.approx(17_000)
    # assembly plants do not pay regional power yet (33.5: data centres; fabs later)
    assert power.kind_index(state, "assembly_plant", "europe", b, d) == 1.0
