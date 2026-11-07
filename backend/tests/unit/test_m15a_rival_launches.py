"""M15a (formulas.md 30.7 V5): rivals keep launching after 2020. Regression tests for the three
fixes: a late startup's product starts with a share of the market's learned features, a
hardware startup launches without a contract (rivals' manufacturing is abstract, 26.1), and a
startup down to one person closes so it no longer holds a startup place."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game
from tst.loader import load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.finance.insolvency import insolvency
from tst.sim.ledger import CASH
from tst.sim.products import formulas as pf
from tst.sim.rivals.startups import found_company, launch_ready
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


def test_a_startup_down_to_one_person_closes() -> None:
    state, cid = _startup(fresh_game(LOADED), "b2b_saas")
    staff = state.staff(cid)
    assert len(staff) > 1
    balances = {(cid, CASH): 10**9}
    kept, _ = insolvency(state, balances, B, D)
    assert kept.company(cid).alive  # a team and cash: still in business
    for e in staff[1:]:
        state = with_employment(state, replace(e, status="ended", end_turn=state.turn))
    closed, _ = insolvency(state, balances, B, D)
    assert not closed.company(cid).alive
    assert all(p.status == "retired" for p in closed.company_products(cid))
