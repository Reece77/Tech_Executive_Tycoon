"""M10r finding 4 (Codex review 2, P2): a product's current MRR, customers and hosting, and
the portfolio's customer counts, include its sales in other regions (19.5). Series that stay
home-only by decision (product history) say so: "home region"."""

from __future__ import annotations

from tests.helpers import fresh_game, with_product
from tst.api.product_views import portfolio_out, product_out
from tst.loader import LoadedData
from tst.sim.geo.models import ProductRegion, RegionalSegment
from tst.sim.products.phases import product_costs, projected_revenue
from tst.sim.state import GameState, with_product_region, with_regional_segment

CUSTOMERS, PRICE = 1_000.0, 4_500  # 1,000 European SMBs at $45 a month


def _europe_only(loaded: LoadedData) -> GameState:
    state = with_product(fresh_game(loaded), customers={"smb": 0.0})
    pid = state.company_products(1)[0].id
    state = with_product_region(state, ProductRegion(pid, "europe", 0, 0))
    seg = RegionalSegment(pid, "europe", "smb", PRICE, CUSTOMERS, False, 0)
    return with_regional_segment(state, seg)


def test_a_product_selling_only_in_europe_shows_its_sales(loaded: LoadedData) -> None:
    state = _europe_only(loaded)
    product = state.company_products(1)[0]
    out = product_out(state, product, [], loaded)
    hosting, _ = product_costs(state, 1, loaded.game_data)
    assert out.mrr_cents == CUSTOMERS * PRICE == projected_revenue(state, 1)
    assert out.customers == CUSTOMERS
    assert out.hosting_cents == hosting > 0
    assert out.series_scope == "home_region"
    assert out.series_label == "Home region"
    assert out.sells_abroad


def test_the_portfolio_agrees_with_company_totals(loaded: LoadedData) -> None:
    state = _europe_only(loaded)
    out = portfolio_out(state, [], "Stage 1", loaded)
    hosting, _ = product_costs(state, 1, loaded.game_data)
    assert out.paying_customers == CUSTOMERS
    assert out.consumer_users == 0
    assert out.hosting_cents == hosting
    product = product_out(state, state.company_products(1)[0], [], loaded)
    assert out.paying_customers == product.customers
