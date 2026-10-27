"""M3a persistence: products, segments, demand and assignments round-trip; older saves get
the 2010 market on upgrade (migration 0008_products)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import select, text

from tst.db import migrate
from tst.db.models import SCHEMA_VERSION, CompanyRow
from tst.db.repository import create_save, load_state, open_session, run_turn
from tst.db.session import make_engine
from tst.db.state_io import sync_state
from tst.loader import LoadedData
from tst.sim.org.models import OrgUnit
from tst.sim.products.models import Product, ProductSegment
from tst.sim.products.setup import addressable_at
from tst.sim.state import with_company, with_product, with_product_segment, with_unit


def _save(tmp_path: Path, loaded: LoadedData) -> Path:
    return create_save(
        "prod", 5, "funded_spinout", company_name="Prod Co", data=loaded, save_dir=tmp_path
    )


def test_new_game_has_every_market_and_incumbent(tmp_path: Path, loaded: LoadedData) -> None:
    with open_session(_save(tmp_path, loaded)) as session:
        state = load_state(session)
    names = [c.name for c in state.companies if not c.is_player]
    assert names == [c.name for c in loaded.game_data.incumbents]
    assert [c.id for c in state.companies] == list(range(1, 14))
    assert len(state.products) == 12 and all(p.status == "live" for p in state.products)
    assert len(state.markets) == sum(len(c.markets) for c in loaded.game_data.categories)
    smb = state.market("b2b_saas", "smb")
    assert smb is not None and smb.addressable == 400_000
    sales_cloud = state.products[0]
    assert (sales_cloud.name, sales_cloud.held_feature) == ("Sales Cloud", 80)
    seg = state.product_segment(sales_cloud.id, "smb")
    assert seg is not None and seg.customers == pytest.approx(40_000)  # 10% (tuned)
    assert state.next_ids.product == 13
    assert state.ledger_companies() == (state.player,)


def test_products_and_assignments_round_trip(tmp_path: Path, loaded: LoadedData) -> None:
    path = _save(tmp_path, loaded)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        product = Product(
            id=13,
            company_id=1,
            category="b2b_saas",
            name="Pipeline",
            status="in_development",
            quality=10,
            feature_points=0,
            brand=0,
            marketing_budget_cents=1_000_000,
            created_turn=0,
        )
        state = with_product(before, product)
        state = with_product_segment(state, ProductSegment(13, "smb", 4000))
        state = with_product_segment(state, ProductSegment(13, "mid_market", None))
        state = with_unit(state, OrgUnit(1, 1, "team", "Core", None, None, None, 0, product_id=13))
        state = with_company(state, replace(state.player, root_product_id=13))
        state = replace(state, next_ids=replace(state.next_ids, product=14, unit=2))
        sync_state(session, before, state)
    with open_session(path) as session:
        loaded_state = load_state(session)
    assert loaded_state.product(13) == product
    assert loaded_state.segments_of(13) == (
        ProductSegment(13, "mid_market", None),
        ProductSegment(13, "smb", 4000),
    )
    assert loaded_state.units[0].product_id == 13
    assert loaded_state.player.root_product_id == 13
    assert loaded_state.next_ids.product == 14


def test_retired_products_leave_the_live_state(tmp_path: Path, loaded: LoadedData) -> None:
    path = _save(tmp_path, loaded)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        retired = replace(before.products[0], status="retired", retired_turn=0)
        sync_state(session, before, with_product(before, retired))
    with open_session(path) as session:
        state = load_state(session)
    assert retired.id not in {p.id for p in state.products}
    assert all(s.product_id != retired.id for s in state.product_segments)


def test_upgrade_from_0007_adds_the_market_at_the_saves_turn(
    tmp_path: Path, loaded: LoadedData
) -> None:
    path = _save(tmp_path, loaded)
    for _ in range(3):
        run_turn(path, loaded)
    migrate.downgrade(path, "0007_plan_focus")
    engine = make_engine(path)
    with engine.connect() as conn:
        companies = conn.execute(text("SELECT COUNT(*) FROM company")).scalar()
    engine.dispose()
    assert companies == 1  # the downgrade removed the incumbents

    assert migrate.ensure_current(path) is not None
    with open_session(path) as session:
        state = load_state(session)
        players = session.scalars(select(CompanyRow).where(CompanyRow.is_player)).all()
    assert len(players) == 1 and len(state.companies) == 13
    assert state.turn == 3
    smb = state.market("b2b_saas", "smb")
    assert smb is not None
    assert smb.addressable == pytest.approx(addressable_at(loaded.game_data, "b2b_saas", "smb", 3))
    assert smb.addressable > 400_000
    seg = state.product_segment(1, "smb")
    assert seg is not None and seg.customers == pytest.approx(0.10 * smb.addressable)
    engine = make_engine(path)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT schema_version FROM save_meta")).scalar()
    engine.dispose()
    assert version == SCHEMA_VERSION
    run_turn(path, loaded)  # the upgraded save keeps playing
