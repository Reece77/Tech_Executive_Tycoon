"""M3a acceptance: 120 turns with 25 staff, 3 products and all incumbents average under 1 s."""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

from tests.helpers import fund_save
from tests.integration.test_api_org import seed_staff
from tst.db.repository import create_save, load_state, open_session, run_action, run_turn
from tst.loader import LoadedData
from tst.sim.actions import (
    AssignUnit,
    CreateProduct,
    CreateUnit,
    LaunchProduct,
    MovePerson,
    SetMarketing,
    SetPrice,
)
from tst.sim.errors import LaunchNotReadyError

STAFF = 24  # employees; 25 with the founder
TURNS = 120
PRODUCTS = (
    ("Pipeline", "b2b_saas", {"smb": 4000, "mid_market": 70_000}),
    ("Forge", "dev_tools", {"smb": 2000, "mid_market": 40_000}),
    ("Shield", "cybersecurity", {"smb": 3000, "enterprise": 1_000_000}),
)


def test_product_turn_time_budget(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "prodperf", 3, "funded_spinout", company_name="Perf Co", data=loaded, save_dir=tmp_path
    )
    fund_save(path, 10**11)  # timing, not solvency: keep the long run out of bankruptcy
    seed_staff(path, loaded, STAFF)
    founder = 1
    for name in ("Forge team", "Shield team"):
        run_action(path, loaded, CreateUnit(founder, "team", name))
    for i, pid in enumerate(range(2, 2 + STAFF)):
        if i % 3:
            run_action(path, loaded, MovePerson(founder, pid, i % 3))
    for index, (name, category, prices) in enumerate(PRODUCTS):
        product = 13 + index
        run_action(path, loaded, CreateProduct(founder, name, category, tuple(prices)))
        for segment, price in prices.items():
            run_action(path, loaded, SetPrice(founder, product, segment, price))
        run_action(path, loaded, AssignUnit(founder, product, None if index == 0 else index))
        run_action(path, loaded, SetMarketing(founder, product, 500_000))
    with open_session(path) as session:
        state = load_state(session)
    assert len(state.staff(1)) == STAFF + 1 and len(state.company_products(1)) == len(PRODUCTS)
    assert len(state.products) == 12 + len(PRODUCTS)

    start = time.perf_counter()
    for _ in range(TURNS):
        with open_session(path) as session:
            state = load_state(session)
        for product in state.company_products(1):
            if product.status == "in_development" and product.quality >= 25:
                with contextlib.suppress(LaunchNotReadyError):  # features not there yet
                    run_action(path, loaded, LaunchProduct(founder, product.id))
        run_turn(path, loaded)
    per_turn = (time.perf_counter() - start) / TURNS
    with open_session(path) as session:
        state = load_state(session)
    live = [p.name for p in state.company_products(1) if p.status == "live"]
    print(
        f"{TURNS} turns: {per_turn * 1000:.0f} ms per turn (load and launch checks included); "
        f"staff {len(state.staff(1))}, products {len(state.products)}, live {live}"
    )
    assert per_turn < 1.0
