"""M8r finding 5 (Codex review 1, P2): the price preview scores the proposed price, the
current price and actual sales against the same reference price, with the CRO's pricing power
in a sales-led segment (18.3). Previewing the unchanged price shows the current appeal and
share exactly, with the CRO seat occupied and vacant."""

from __future__ import annotations

import pytest

from tests.helpers import with_product
from tests.unit.test_scaleup import FOUNDER, game, run, skilled
from tst.api.product_views import price_preview
from tst.loader import LoadedData
from tst.sim.actions import AppointExecutive

PRICE = 80_000  # the mid-market reference price: $800


@pytest.mark.parametrize("cro", [True, False], ids=["cro-occupied", "cro-vacant"])
def test_an_unchanged_price_previews_the_current_appeal(loaded: LoadedData, cro: bool) -> None:
    state = with_product(game(loaded, staff=2), prices={"mid_market": PRICE}, quality=50.0)
    if cro:
        state = run(loaded, skilled(state, 2, 14.0), AppointExecutive(FOUNDER, "cro", 2))
    product = state.products[-1]
    out = price_preview(state, product, "mid_market", PRICE, loaded)
    assert out.price_score == out.current_price_score
    assert out.appeal == out.current_appeal
    assert out.choice_share == out.current_choice_share
