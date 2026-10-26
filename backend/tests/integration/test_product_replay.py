"""Replay reproduces a save with products, price changes and assignments (ADR-0014)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from tests.golden.test_golden import snapshots
from tst.db.models import ProductMonthRow
from tst.db.repository import (
    create_save,
    load_state,
    open_session,
    replay_save,
    run_action,
    run_turn,
)
from tst.loader import LoadedData
from tst.sim.actions import (
    AddSegment,
    AssignUnit,
    CreateProduct,
    CreateUnit,
    Interview,
    LaunchProduct,
    MakeOffer,
    MovePerson,
    OpenSearch,
    SetMarketing,
    SetPrice,
    UnassignUnit,
)
from tst.sim.actions.products import launch_problems

PRODUCT = 13


def build(tmp_path: Path, loaded: LoadedData) -> Path:
    path = create_save(
        "prodrep", 17, "funded_spinout", company_name="Rep Co", data=loaded, save_dir=tmp_path
    )
    # Hire through actions: replay rebuilds the save from logged actions only.
    run_action(path, loaded, OpenSearch(1, "software_engineer", "job_post"))
    run_turn(path, loaded)
    with open_session(path) as session:
        state = load_state(session)
    for candidate in state.candidates[:4]:
        ask = state.person(candidate.person_id).salary_expectation_cents or 0
        run_action(path, loaded, Interview(1, candidate.person_id))
        run_action(path, loaded, MakeOffer(1, candidate.person_id, round(ask * 1.3), 0))
    run_action(path, loaded, CreateProduct(1, "Pipeline", "b2b_saas", ("smb",)))
    run_action(path, loaded, SetPrice(1, PRODUCT, "smb", 4500))
    run_action(path, loaded, AssignUnit(1, PRODUCT, None))
    run_action(path, loaded, SetMarketing(1, PRODUCT, 800_000))
    for turn in range(1, 16):
        with open_session(path) as session:
            state = load_state(session)
        product = state.product(PRODUCT)
        assert product is not None
        if product.status == "in_development" and not launch_problems(
            state, product, loaded.balance, loaded.game_data
        ):
            run_action(path, loaded, LaunchProduct(1, PRODUCT))
        if turn == 7:
            run_action(path, loaded, SetPrice(1, PRODUCT, "smb", 3500))
            run_action(path, loaded, AddSegment(1, PRODUCT, "mid_market"))
            run_action(path, loaded, SetPrice(1, PRODUCT, "mid_market", 60_000))
        if turn == 10:
            run_action(path, loaded, CreateUnit(1, "team", "Core"))
            hired = sorted(e.person_id for e in state.staff(1) if e.person_id != 1)
            run_action(path, loaded, MovePerson(1, hired[0], 1))
            run_action(path, loaded, AssignUnit(1, PRODUCT, 1))
            run_action(path, loaded, UnassignUnit(1, None))
        run_turn(path, loaded)
    return path


def history(path: Path) -> list[tuple[object, ...]]:
    with open_session(path) as session:
        rows = session.scalars(
            select(ProductMonthRow).order_by(
                ProductMonthRow.turn, ProductMonthRow.product_id, ProductMonthRow.segment
            )
        ).all()
        return [
            (r.turn, r.product_id, r.segment, r.quality, r.customers, r.revenue_cents) for r in rows
        ]


def test_replay_reproduces_products(tmp_path: Path, loaded: LoadedData) -> None:
    source = build(tmp_path / "a", loaded)
    replayed = replay_save(source, tmp_path / "b", "prodrep", loaded)
    with open_session(source) as a, open_session(replayed) as b:
        first, second = load_state(a), load_state(b)
    product = first.product(PRODUCT)
    assert product is not None and product.status == "live"
    assert first.products == second.products
    assert first.product_segments == second.product_segments
    assert first.markets == second.markets
    assert first.units == second.units and first.player == second.player
    assert snapshots(source) == snapshots(replayed)
    assert history(source) == history(replayed)
    assert any(r[5] for r in history(source))  # it earned revenue
