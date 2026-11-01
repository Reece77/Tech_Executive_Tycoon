"""M10r finding 5 (Codex review 2, P2): regional prices are money. `p_ref x index_region /
index_home (x a rival's personality factor)` runs on the exact decimals the data was written
as and rounds half-to-even once (ADR-0003, 19.5, 19.6)."""

from __future__ import annotations

from dataclasses import replace

from tests.helpers import fresh_game, with_product
from tst.loader import LoadedData
from tst.sim.geo import formulas as gf
from tst.sim.rivals.decisions import enter_region
from tst.sim.rivals.startups import sell_first_in


def test_an_east_asia_hq_prices_into_south_and_southeast_asia(loaded: LoadedData) -> None:
    # 5000 x 0.35 / 0.80 = 2187.5 -> 2188 (the float ratio 0.43749999999999994 gave 2187)
    price = gf.regional_price_cents(5000, "south_southeast_asia", "east_asia", loaded.game_data)
    assert price == 2188


def _ai_startup(loaded: LoadedData):  # type: ignore[no-untyped-def]
    state = with_product(fresh_game(loaded), category="ai_models", prices={"consumer": 50})
    company = replace(state.player, personality="cost_leader")
    return state, company, state.company_products(1)[0]


def test_a_cost_leader_ai_startup_sells_first_in_europe_at_32(loaded: LoadedData) -> None:
    # 50 x 0.90 x 0.7 = 31.5 -> 32 (45 x the float 0.7 rounded to 31)
    state, company, product = _ai_startup(loaded)
    after = sell_first_in(state, company, product.id, "europe", loaded.balance, loaded.game_data)
    (row,) = after.regional_segments_of(product.id, "europe")
    assert row.price_cents == 32


def test_a_cost_leader_entering_europe_prices_at_32(loaded: LoadedData) -> None:
    state, company, product = _ai_startup(loaded)
    after, _ = enter_region(state, company, product, "europe", loaded.balance, loaded.game_data)
    (row,) = after.regional_segments_of(product.id, "europe")
    assert row.price_cents == 32
