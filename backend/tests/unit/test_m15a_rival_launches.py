"""M15a (formulas.md 30.7 V5): rivals keep launching after 2020. Regression tests for the three
fixes: a late startup's product starts with a share of the market's learned features, a
hardware startup launches without a contract (rivals' manufacturing is abstract, 26.1), and a
startup below three people for 24 months closes so it no longer holds a startup place."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game
from tst.loader import load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.finance.insolvency import insolvency
from tst.sim.ledger import CASH
from tst.sim.products import formulas as pf
from tst.sim.rivals.startups import found_company, launch_ready, record_failures
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_employment, with_product

LOADED = load_all(DATA_DIR)
B, D = LOADED.balance, LOADED.game_data


def _startup(state: GameState, category: str) -> tuple[GameState, int]:
    cat = D.category(category)
    state, company, _ = found_company(
        state,
        "Testco",
        "aggressive",
        cat,
        [cat.segment_keys[0]],
        10**8,
        ["builder", "builder", "builder"],
        ["senior", "mid", "mid"],
        RngFactory(1),
        B,
        D,
    )
    return state, company.id


def test_a_late_startup_starts_with_a_share_of_learned_features() -> None:
    early = fresh_game(LOADED)
    state, cid = _startup(early, "b2b_saas")
    assert state.company_products(cid)[0].feature_points == 0.0  # January 2010: unchanged
    late = replace(fresh_game(LOADED), turn=ym_to_turn(2030, 1))
    state, cid = _startup(late, "b2b_saas")
    cat = D.category("b2b_saas")
    gained = pf.expected_features(cat, late.turn) - cat.features_at_start
    product = state.company_products(cid)[0]
    share = B.rivals.startup.start_feature_share
    assert share > 0 and product.feature_points == pytest.approx(share * gained)


def test_a_hardware_startup_launches_without_a_contract() -> None:
    state, cid = _startup(fresh_game(LOADED), "chips_ai_accelerator")
    (product,) = state.company_products(cid)
    cat = D.category(product.category)
    ready = replace(
        product,
        quality=100.0,
        feature_points=pf.held_feature_points(100.0, cat, state.turn),
    )
    state, moves = launch_ready(with_product(state, ready), B, D)
    assert state.product(product.id).status == "live", "rivals' manufacturing is abstract"
    assert any(m.action == "launched" for m in moves)


def test_a_startup_small_for_24_months_closes() -> None:
    """Product manager's rule (2026-11-07): below rivals.startup.small_staff people for
    rivals.startup.small_months consecutive month ends, a startup closes; History says why."""
    sb = B.rivals.startup
    state, cid = _startup(fresh_game(LOADED), "b2b_saas")
    staff = state.staff(cid)
    assert len(staff) >= sb.small_staff
    balances = {(cid, CASH): 10**9}
    kept, _ = insolvency(state, balances, B, D)
    assert kept.company(cid).alive and kept.company(cid).small_since_turn is None
    for e in staff[sb.small_staff - 1 :]:  # down to one fewer than small_staff
        state = with_employment(state, replace(e, status="ended", end_turn=state.turn))
    start = state.turn
    for month in range(sb.small_months):
        state = replace(state, turn=start + month)
        state, _ = insolvency(state, balances, B, D)
        alive = state.company(cid).alive
        assert alive == (month < sb.small_months - 1), month
    assert state.company(cid).small_since_turn == start
    assert all(p.status == "retired" for p in state.company_products(cid))
    _, moves = record_failures(state, _failed_logs(state, cid))
    assert "tiny team" in moves[0].detail


def test_growing_again_resets_the_small_count() -> None:
    sb = B.rivals.startup
    state, cid = _startup(fresh_game(LOADED), "b2b_saas")
    staff = state.staff(cid)
    small = state
    for e in staff[sb.small_staff - 1 :]:
        small = with_employment(small, replace(e, status="ended", end_turn=small.turn))
    small, _ = insolvency(small, {(cid, CASH): 10**9}, B, D)
    assert small.company(cid).small_since_turn == small.turn
    grown = replace(small, employments=state.employments)  # the team is back
    grown, _ = insolvency(grown, {(cid, CASH): 10**9}, B, D)
    assert grown.company(cid).small_since_turn is None


def _failed_logs(state: GameState, cid: int):  # type: ignore[no-untyped-def]
    from tst.sim.log import inbox_item

    return (inbox_item(state.turn, cid, "rival_failed", rival=state.company(cid).name),)


def test_the_small_count_survives_a_save(tmp_path: Path) -> None:
    """startup_small (migration 0036) round-trips small_since_turn."""
    from tst.db.repository import create_save, open_session
    from tst.db.state_io import load_state, sync_state
    from tst.sim.state import with_company

    path = create_save(
        "small", 3, "funded_spinout", company_name="Co", data=LOADED, save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        before = load_state(session)
        rival = next(c for c in before.companies if not c.is_player)
        sync_state(session, before, with_company(before, replace(rival, small_since_turn=7)))
    with open_session(path) as session:
        assert load_state(session).company(rival.id).small_since_turn == 7
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, with_company(before, replace(rival, small_since_turn=None)))
    with open_session(path) as session:
        assert load_state(session).company(rival.id).small_since_turn is None


def test_ranking_ties_never_favour_the_player() -> None:
    """M15a fix (ruling 5): a tie on a list goes by revenue, then by the stable rival key, and
    the player comes after a rival it ties with (ties went to the lowest id, the player's)."""
    from tst.sim.modes.rankings import lists
    from tst.sim.state import with_company

    state = fresh_game(LOADED)
    rival = next(c for c in state.companies if c.is_rival and state.company_products(c.id))
    same = (100_000,) * 12
    state = with_company(state, replace(state.player, mrr_history=same))
    state = with_company(state, replace(rival, mrr_history=same))
    copy = replace(state.company_products(rival.id)[0], id=10_000, company_id=state.player.id)
    state = with_product(state, copy)  # the player sells the same kind of product
    for p in state.products:
        if p.company_id in (state.player.id, rival.id):
            state = with_product(state, replace(p, status="live", launched_turn=state.turn))
    others = [c for c in state.companies if c.id not in (state.player.id, rival.id)]
    state = replace(state, companies=(state.player, state.company(rival.id), *others))
    innovative = dict(lists(state, B, D)["innovative"])
    assert innovative[state.player.id] == innovative[rival.id]
    order = [cid for cid, _ in lists(state, B, D)["innovative"]]
    assert order.index(rival.id) < order.index(state.player.id)
