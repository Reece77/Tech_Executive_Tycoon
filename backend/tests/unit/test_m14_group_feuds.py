"""The lane merge's feud rules (product manager, 2026-11-05; 28.5 and 29.4): companies in the
player's group are never rivals for feuds, statements, jabs or head-to-head launches; a feud
resets at closing; people who move because of an acquisition never count as poaching."""

from __future__ import annotations

from dataclasses import replace

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game, with_product
from tst.loader import load_all
from tst.sim.rivals import characters, poaching
from tst.sim.rivals.models import RivalMove
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, feud_of, with_company, with_employment

LOADED = load_all(DATA_DIR)
B, D = LOADED.balance, LOADED.game_data
CID = 1


def _as_brand(state: GameState, company_id: int) -> GameState:
    return with_company(state, replace(state.company(company_id), parent_id=CID))


def _overlap() -> tuple[GameState, int, int]:
    """The player selling in smb, and a rival product in the same category and segment."""
    state = with_product(fresh_game(LOADED), customers={"smb": 10.0})
    mine = state.company_products(CID)[0]
    rival_product = next(
        p
        for p in state.products
        if p.company_id != CID
        and p.category == mine.category
        and state.product_segment(p.id, "smb") is not None
    )
    return state, rival_product.company_id, rival_product.id


def test_a_kept_brand_is_never_a_feud() -> None:
    state, rid, _ = _overlap()
    brand = _as_brand(state, rid)
    assert characters.in_player_group(brand, rid)
    assert feud_of(characters.add_feud(brand, CID, rid, 30, "test", B), CID, rid) is None
    # the same rival outside the group does feud
    assert feud_of(characters.add_feud(state, CID, rid, 30, "test", B), CID, rid) is not None


def test_a_kept_brand_neither_speaks_nor_jabs() -> None:
    state, rid, pid = _overlap()
    move = RivalMove(1, rid, state.turn, "price_cut", pid, "smb", "")
    spoke = [characters.feud_month(state, RngFactory(seed), B, D, (move,))[0] for seed in range(20)]
    assert any(s.statements for s in spoke), "the rival speaks on some seed"
    brand = _as_brand(state, rid)
    for seed in range(20):
        out, logs = characters.feud_month(brand, RngFactory(seed), B, D, (move,))
        assert not out.statements and not logs
        assert not any(m.trigger == "jab" for m in out.press_moments)


def test_a_launch_against_a_kept_brand_is_not_head_to_head() -> None:
    state, rid, _ = _overlap()
    mine = state.company_products(CID)[0]
    launched = with_product_turn(state, mine.id)
    out, _ = characters.feud_month(launched, RngFactory(1), B, D, ())
    assert feud_of(out, CID, rid) is not None  # a rival in the segment
    out, _ = characters.feud_month(_as_brand(launched, rid), RngFactory(1), B, D, ())
    assert feud_of(out, CID, rid) is None


def with_product_turn(state: GameState, product_id: int) -> GameState:
    from tst.sim.state import with_product as put

    product = state.product(product_id)
    assert product is not None
    return put(state, replace(product, launched_turn=state.turn))


def test_closing_resets_the_feud() -> None:
    state, rid, _ = _overlap()
    state = characters.add_feud(state, CID, rid, 40, "test", B)
    out = characters.reset_feud(state, rid)
    feud = feud_of(out, CID, rid)
    assert feud is not None and feud.score == 0 and feud.causes  # the history stays


def test_an_acquisition_move_is_not_poaching() -> None:
    state, rid, _ = _overlap()
    old = state.staff(rid)[0]
    moved = with_employment(
        state, replace(old, status="ended", end_turn=state.turn, end_reason="acquired")
    )
    eid, ids = moved.next_ids.take("employment")
    moved = with_employment(
        replace(moved, next_ids=ids),
        replace(old, id=eid, company_id=CID, start_turn=state.turn, end_turn=None, unit_id=None),
    )
    out, _ = characters.feud_month(moved, RngFactory(1), B, D, ())
    assert POACH not in _causes(out, rid)
    # the same hire as an ordinary poach does feed the feud
    poached = with_employment(moved, replace(old, status="ended", end_turn=state.turn))
    out, _ = characters.feud_month(poached, RngFactory(1), B, D, ())
    assert POACH in _causes(out, rid)


POACH = "you hired one of their people"


def _causes(state: GameState, rid: int) -> list[str]:
    feud = feud_of(state, CID, rid)
    return [c for _, _, c in feud.causes] if feud is not None else []


def test_taking_a_brands_key_person_ends_their_job_as_acquired() -> None:
    state, rid, _ = _overlap()
    person = state.staff(rid)[0].person_id
    out = poaching.leave_rival(_as_brand(state, rid), person, B, D)
    ended = next(e for e in out.employments if e.person_id == person and e.company_id == rid)
    assert ended.end_reason == "acquired"
    out = poaching.leave_rival(state, person, B, D)
    ended = next(e for e in out.employments if e.person_id == person and e.company_id == rid)
    assert ended.end_reason == "poached"
