"""M10b regions (docs/formulas.md 23.5): self-serve sells abroad at full awareness without a
local presence; a product's marketing can be split by region (by revenue unless set); a region
with no marketing gets 70% of the global awareness."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.unit.test_geo_markets import FOUNDER, PRODUCT, _act, _live
from tst.loader import LoadedData
from tst.sim.actions.geo import SetMarketingSplit
from tst.sim.errors import GeoRuleError
from tst.sim.geo import marketing as mk
from tst.sim.geo.markets import reach_context
from tst.sim.geo.models import ProductRegion, RegionalSegment
from tst.sim.state import GameState, with_product_region, with_regional_segment


def _abroad(loaded: LoadedData, europe_customers: float = 100.0) -> GameState:
    """Home SMB at $40 (900 customers) and Europe SMB at $40 live: revenue 90% / 10%."""
    state = _live(loaded)
    seg = state.segments_of(PRODUCT)[0]
    state = replace(
        state,
        product_segments=tuple(
            replace(s, customers=900.0) if s.product_id == PRODUCT else s
            for s in state.product_segments
        ),
    )
    state = with_product_region(state, ProductRegion(PRODUCT, "europe", 0, 0))
    return with_regional_segment(
        state, RegionalSegment(PRODUCT, "europe", seg.segment, 4_000, europe_customers)
    )


def test_self_serve_needs_no_presence(loaded: LoadedData) -> None:
    geo = reach_context(_live(loaded), loaded.balance, loaded.game_data)
    assert geo is not None and geo.awareness_factor(1, "europe") == 1.0


def test_the_default_split_follows_revenue_at_full_awareness(loaded: LoadedData) -> None:
    state = _abroad(loaded)
    product = state.product(PRODUCT)
    assert product is not None
    assert mk.split(state, product, "north_america") == pytest.approx(
        {"north_america": 0.9, "europe": 0.1}
    )
    assert mk.awareness_factors(state, product, "north_america", loaded.balance) == {
        "north_america": 1.0,
        "europe": 1.0,
    }


def test_a_split_moves_awareness_and_no_spend_is_70_percent(loaded: LoadedData) -> None:
    b, data = loaded.balance, loaded.game_data
    state = _act(
        loaded, _abroad(loaded), SetMarketingSplit(FOUNDER, PRODUCT, (("north_america", 10_000),))
    ).new_state
    geo = reach_context(state, b, data)
    assert geo is not None
    assert geo.awareness_factor(1, "europe", PRODUCT) == 0.7
    assert geo.awareness_factor(1, "north_america", PRODUCT) == 1.0
    even = _act(
        loaded,
        _abroad(loaded),
        SetMarketingSplit(FOUNDER, PRODUCT, (("europe", 5_000), ("north_america", 5_000))),
    ).new_state
    geo = reach_context(even, b, data)
    assert geo is not None
    assert geo.awareness_factor(1, "europe", PRODUCT) == 1.0  # more than its revenue share
    assert geo.awareness_factor(1, "north_america", PRODUCT) == pytest.approx(0.7 + 0.3 * 5 / 9)
    reset = _act(loaded, even, SetMarketingSplit(FOUNDER, PRODUCT, ())).new_state
    assert reset.marketing_splits == ()


def test_split_rules(loaded: LoadedData) -> None:
    state = _abroad(loaded)
    for shares in (
        (("north_america", 6_000), ("europe", 3_000)),  # not 100%
        (("north_america", 5_000), ("east_asia", 5_000)),  # not selling there
        (("north_america", 12_000), ("europe", -2_000)),  # negative
    ):
        with pytest.raises(GeoRuleError):
            _act(loaded, state, SetMarketingSplit(FOUNDER, PRODUCT, shares))


def test_a_home_only_product_is_unchanged(loaded: LoadedData) -> None:
    state = _live(loaded)
    product = state.product(PRODUCT)
    assert product is not None
    assert mk.awareness_factors(state, product, "north_america", loaded.balance) == {}
