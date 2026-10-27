"""M4a persistence: the cap table, grants, SAFEs, rounds, term sheets, board seats and the
game state round-trip; older saves get their cap table on upgrade (migration 0009_finance)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from sqlalchemy import text

from tests.helpers import make_person, move_save_directors, with_employee
from tst.db import migrate
from tst.db.models import SCHEMA_VERSION
from tst.db.repository import create_save, load_state, open_session, run_turn
from tst.db.state_io import sync_state
from tst.loader import LoadedData
from tst.sim.finance.board import BOARD_ROLE
from tst.sim.finance.captable import fd_shares, share_price, unallocated
from tst.sim.finance.models import FundingRound, OptionGrant, Safe, TermSheet
from tst.sim.state import (
    with_grant,
    with_person,
    with_round,
    with_safe,
    with_seat,
    with_term_sheet,
)


def _save(tmp_path: Path, loaded: LoadedData, scenario: str = "funded_spinout") -> Path:
    return create_save("fin", 5, scenario, company_name="Fin Co", data=loaded, save_dir=tmp_path)


def test_funded_spinout_starts_with_its_seed_and_board(tmp_path: Path, loaded: LoadedData) -> None:
    with open_session(_save(tmp_path, loaded)) as session:
        state = load_state(session)
    assert fd_shares(state, 1) == 10_000_000 and unallocated(state, 1) == 1_000_000
    assert share_price(state, 1) == 75  # cents a share
    (seed,) = state.rounds
    assert (seed.series, seed.status, seed.lead_firm, seed.post_money_cents) == (
        "seed",
        "closed",
        "first_round",
        750_000_000,
    )
    founder_seat, investor = state.seats
    assert (founder_seat.kind, founder_seat.person_id, founder_seat.confidence) == (
        "common",
        1,
        None,
    )
    assert (investor.kind, investor.firm, investor.confidence) == ("investor", "first_round", 70)
    director = state.person(investor.person_id)
    assert director.role == BOARD_ROLE and state.employment_of(director.id) is None
    assert state.next_ids.person == director.id + 1


def test_finance_state_round_trips(tmp_path: Path, loaded: LoadedData) -> None:
    path = _save(tmp_path, loaded)
    move_save_directors(path)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        person = make_person(loaded, 2)
        state = with_person(with_employee(loaded, before, person, 9_000_000, equity_bp=50), person)
        state = with_grant(state, OptionGrant(1, 1, 2, 2, 50_000, 0))
        state = with_safe(state, Safe(1, 1, "safe", 50_000_000, 500_000_000, "pending", 0))
        state = with_safe(
            state, Safe(2, 1, "bridge", 9_000_000, 600_000_000, "offered", 0, expires_turn=2)
        )
        state = with_round(state, FundingRound(2, 1, "a", "open", 500_000_000, 0, 2))
        state = with_term_sheet(
            state, TermSheet(1, 2, "accel", 1_600_000_000, 500_000_000, "offered", 0, 2)
        )
        state = with_seat(state, replace(state.seats[1], confidence=41.5, months_below=2))
        state = replace(
            state,
            save_meta=replace(state.save_meta, game_state="bankrupt", ended_turn=0),
            companies=tuple(
                replace(c, mrr_history=(0, 100, 250), insolvent_months=2) if c.is_player else c
                for c in state.companies
            ),
            next_ids=replace(state.next_ids, person=3, grant=2, safe=3, round=3, term_sheet=2),
        )
        sync_state(session, before, state)
    with open_session(path) as session:
        back = load_state(session)
    for name in ("grants", "safes", "rounds", "term_sheets", "seats", "cap_entries"):
        assert getattr(back, name) == getattr(state, name), name
    assert (back.save_meta.game_state, back.save_meta.ended_turn) == ("bankrupt", 0)
    assert (back.player.mrr_history, back.player.insolvent_months) == ((0, 100, 250), 2)
    assert back.next_ids == state.next_ids


def test_upgrade_from_0008_converts_equity_to_options(tmp_path: Path, loaded: LoadedData) -> None:
    path = _save(tmp_path, loaded, "ex_big_tech_founders")
    with open_session(path) as session, session.begin():
        before = load_state(session)
        person = make_person(loaded, 2)
        state = with_person(with_employee(loaded, before, person, 9_000_000, equity_bp=50), person)
        state = replace(state, next_ids=replace(state.next_ids, person=3))
        sync_state(session, before, state)
    for _ in range(13):
        run_turn(path, loaded)
    migrate.downgrade(path, "0008_products")
    assert migrate.ensure_current(path) is not None
    with open_session(path) as session:
        state = load_state(session)
        version = session.execute(text("SELECT schema_version FROM save_meta")).scalar()
    assert version == SCHEMA_VERSION  # upgraded through 0009 to the head
    (grant,) = state.grants
    assert (grant.person_id, grant.granted, grant.start_turn) == (2, 50_000, 0)
    assert grant.vested == 50_000 * 13 // 48  # 13 months served
    assert unallocated(state, 1) == 950_000 and fd_shares(state, 1) == 10_000_000
    assert [e.name for e in state.cap_entries if e.holder_kind == "group"] == ["Former colleagues"]
    assert len(state.player.mrr_history) == 13 and state.seats == ()
    run_turn(path, loaded)  # the upgraded save keeps playing


def test_upgrade_gives_a_funded_spinout_its_board(tmp_path: Path, loaded: LoadedData) -> None:
    path = _save(tmp_path, loaded)
    run_turn(path, loaded)
    migrate.downgrade(path, "0008_products")
    assert migrate.ensure_current(path) is not None
    with open_session(path) as session:
        state = load_state(session)
    assert [s.kind for s in state.seats] == ["common", "investor"]
    director = state.person(state.seats[1].person_id)
    assert director.role == BOARD_ROLE
    assert share_price(state, 1) == 75 and state.rounds[0].lead_firm == "first_round"
    run_turn(path, loaded)
