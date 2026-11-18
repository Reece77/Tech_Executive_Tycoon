"""M43a (formulas.md 54.1, acceptance): from 2026 no market grows past its ceiling, from any
starting size; one that starts past it is held, never cut."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities.compute import home_region_of
from tst.sim.markets import saturation as sat
from tst.sim.products.phases import brand_and_demand
from tst.sim.state import GameState

TOLERANCE = 1e-9


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    scale=st.floats(min_value=0.01, max_value=1e4),
    year=st.integers(min_value=2026, max_value=2060),
    months=st.integers(min_value=1, max_value=6),
)
def test_no_market_passes_its_ceiling(
    loaded: LoadedData, scale: float, year: int, months: int
) -> None:
    data, balance = loaded.game_data, loaded.balance
    state = fresh_game(loaded)
    state = replace(
        state,
        turn=ym_to_turn(year, 1),
        markets=tuple(replace(m, addressable=m.addressable * scale) for m in state.markets),
        regional_markets=tuple(
            replace(m, addressable=m.addressable * scale) for m in state.regional_markets
        ),
    )
    home = home_region_of(state, balance, data)

    def values_of(s: GameState) -> dict[sat.Key, float]:
        rows = [(m.category, m.segment, home, m.addressable) for m in s.markets]
        rows += [(r.category, r.segment, r.region, r.addressable) for r in s.regional_markets]
        return sat.market_values(s, rows, data, home)

    for _ in range(months):
        before = values_of(state)
        state = brand_and_demand(state, balance, data)
        for (cat, region), v in values_of(state).items():
            if not sat.grows(data, cat):
                continue
            cap = sat.ceiling_cents(state, balance, data, cat, region)
            limit = max(cap, before[(cat, region)])
            assert v <= limit * (1 + TOLERANCE), (cat, region, v, cap)
            if before[(cat, region)] > cap:  # past it: held, not cut
                assert v == pytest.approx(before[(cat, region)], rel=1e-9)
        state = replace(state, turn=state.turn + 1)
