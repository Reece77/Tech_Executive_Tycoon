"""M10b sub-task 1 (Reece's playtest): a price set for a region shows in the product's prices
panel and the Regions panel, read back from the save, and is the price charged (19.5)."""

from __future__ import annotations

from pathlib import Path

from tests.helpers import play_turn
from tests.integration.test_api_geo import BASE, PRODUCT, api  # noqa: F401
from tests.integration.test_api_hiring import Client
from tst.db.repository import open_session
from tst.db.state_io import load_state
from tst.loader import LoadedData

PRICE = 3_900


def test_a_regional_price_shows_and_is_charged(
    api: tuple[Client, Path],  # noqa: F811
    loaded: LoadedData,
) -> None:
    client, path = api
    client.post(f"{BASE}/products/{PRODUCT}/regions", {"region": "europe"})
    client.post(
        f"{BASE}/products/{PRODUCT}/regions/europe/price",
        {"segment": "smb", "price_cents": PRICE},
    )
    for _ in range(loaded.balance.markets.localize_months + 1):
        play_turn(path, loaded)
    regions = client.get(f"{BASE}/products/{PRODUCT}/regions")
    europe = next(r for r in regions["regions"] if r["region"] == "europe")
    assert europe["status"] == "live"
    assert europe["segments"][0]["price_cents"] == PRICE
    product = client.get(f"{BASE}/products/{PRODUCT}")
    shown = [p for p in product["regional_prices"] if p["region"] == "europe"]
    assert [(p["segment"], p["price_cents"]) for p in shown] == [("smb", PRICE)]
    with open_session(path) as session:
        state = load_state(session)
    (seg,) = state.regional_segments_of(PRODUCT, "europe")
    assert seg.price_cents == PRICE
    assert europe["segments"][0]["mrr_cents"] == round(seg.customers * PRICE)
