"""M43a (formulas.md 54.1, acceptance): no market passes its ceiling, from any starting size."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities.compute import home_region_of
from tst.sim.markets import saturation as sat
from tst.sim.products.phases import brand_and_demand

TOLERANCE = 1e-9


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    scale=st.floats(min_value=0.01, max_value=1e4),
    year=st.integers(min_value=2010, max_value=2025),
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
    for _ in range(months):
        state = brand_and_demand(state, balance, data)
        rows = [(m.category, m.segment, home, m.addressable) for m in state.markets]
        rows += [(r.category, r.segment, r.region, r.addressable) for r in state.regional_markets]
        values = sat.market_values(state, rows, data, home)
        for (cat, region), v in values.items():
            if not sat.grows(data, cat):
                continue
            cap = sat.ceiling_cents(state, balance, data, cat, region)
            assert v <= cap * (1 + TOLERANCE), (cat, region, v, cap)
        state = replace(state, turn=state.turn + 1)
