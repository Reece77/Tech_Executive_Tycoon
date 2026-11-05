"""M14b rival CEOs and feuds (29.4) and the recruitment fixes (29.5): Replace, search by
interest with its fee, and leadership fit from revealed values only."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game, make_person, with_employee
from tst.loader import load_all
from tst.sim.actions import OpenSearch, ReplaceLeaver, apply_action
from tst.sim.hiring import phases
from tst.sim.hiring.recruit import interest_fee_cents, leadership_fit, replace_problem
from tst.sim.ledger import CASH, RECRUITING
from tst.sim.org.replace import replace_offers
from tst.sim.people.reveal import revealed_range
from tst.sim.press.names import rival_ceo_id
from tst.sim.rivals import characters
from tst.sim.rivals.models import RivalMove
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, feud_of, with_employment

LOADED = load_all(DATA_DIR)
B, D = LOADED.balance, LOADED.game_data
CID = 1
CASH_ = {(CID, CASH): 10**12}


def _rival(state: GameState) -> int:
    return next(c.id for c in state.companies if c.is_rival and state.staff(c.id))


# --- Rival CEOs and feuds (29.4) ------------------------------------------------------------------


def test_rival_ceo_is_the_highest_leadership() -> None:
    state = fresh_game(LOADED)
    rid = _rival(state)
    ceo = rival_ceo_id(state, rid)
    best = max(state.staff(rid), key=lambda e: state.person(e.person_id).skills["leadership"])
    assert ceo == best.person_id
    # succession: the CEO leaves and the next is chosen
    gone = with_employment(state, replace(state.employment_of(ceo), status="ended"))  # type: ignore[arg-type]
    assert rival_ceo_id(gone, rid) not in (None, ceo)


def test_feud_sources_decay_and_rivalry() -> None:
    fb = B.feud
    state = fresh_game(LOADED)
    rid = _rival(state)
    state, _ = characters.bold_mention(state, CID, rid, B, D)
    state = characters.add_feud(state, CID, rid, fb.head_to_head, "launch", B)
    feud = feud_of(state, CID, rid)
    below = fb.bold_mention + fb.head_to_head
    assert below < fb.rivalry
    assert feud is not None and feud.score == below and not characters.in_rivalry(state, rid, B)
    state = characters.add_feud(state, CID, rid, fb.poach, "poached", B)
    state = characters.add_feud(state, CID, rid, fb.poach, "poached", B)
    feud = feud_of(state, CID, rid)
    score = below + 2 * fb.poach
    assert feud is not None and feud.score == score and feud.rivalry_turn == state.turn
    assert characters.rivalry_mult(state, rid, B) == fb.target_mult == 1.5
    assert any(m.trigger == "rivalry" and m.rival_id == rid for m in state.press_moments)
    assert len(feud.causes) == min(4, fb.causes_kept)
    state, _ = characters.feud_month(state, RngFactory(1), B, D, ())
    assert feud_of(state, CID, rid).score == score - fb.decay  # type: ignore[union-attr]


def test_jab_opens_a_moment_when_both_sell() -> None:
    from tests.helpers import with_product

    state = with_product(fresh_game(LOADED), customers={"smb": 10.0})
    mine = state.company_products(CID)[0]
    rival_product = next(
        p for p in state.products if p.company_id != CID and p.category == mine.category
    )
    rid = rival_product.company_id
    state = characters.add_feud(state, CID, rid, 100, "test", B)  # the jab chance is at its top
    move = RivalMove(1, rid, state.turn, "price_cut", rival_product.id, "smb", "")
    jabbed = [
        s
        for seed in range(20)
        for s in [characters.feud_month(state, RngFactory(seed), B, D, (move,))[0]]
        if any(m.trigger == "jab" for m in s.press_moments)
    ]
    assert jabbed, "a jab within 20 seeds at feud 100"
    out = jabbed[0]
    assert any(st.kind == "jab" and st.rival_id == rid for st in out.statements)


def test_rival_choose_weights_against_the_player_in_a_rivalry() -> None:
    from tests.helpers import with_product
    from tst.sim.rivals.decisions import Candidate, _against_player, _player_markets

    state = with_product(fresh_game(LOADED))
    mine = state.company_products(CID)[0]
    rival_product = next(
        p for p in state.products if p.company_id != CID and p.category == mine.category
    )
    markets = _player_markets(state)
    assert _against_player(state, Candidate("price_cut", 1.0, rival_product.id, "smb"), markets)
    assert _against_player(state, Candidate("poach", 1.0), markets)
    assert not _against_player(state, Candidate("cut_costs", 1.0), markets)


# --- Leadership fit (29.5): revealed values only ------------------------------------------------


def test_leadership_fit_from_revealed_ranges_only() -> None:
    state = with_employee(LOADED, fresh_game(LOADED), make_person(LOADED, 2, level="senior"), 10**7)
    person = state.person(2)
    reveal = state.reveal(CID, 2)
    assert reveal is not None
    lo, hi = leadership_fit(person, reveal, B)
    assert 1 <= lo <= hi <= 5
    # the fit is a function of the revealed ranges: true values that show the same ranges give
    # the same fit (shift the true values and the offsets together)
    ranges = {k: revealed_range(person, reveal, k) for k in B.recruit.fit_weights}
    other = replace(
        person,
        skills=person.skills.updated(
            {
                k: min(20.0, person.skills[k] + 0.4)
                for k in ("leadership", "mentoring", "communication")
            }
        ),
    )
    same = all(revealed_range(other, reveal, k) == ranges[k] for k in B.recruit.fit_weights)
    if same:
        assert leadership_fit(other, reveal, B) == (lo, hi)
    assert leadership_fit(person, None, B) == (1, 5)


# --- Search by interest (29.5) ------------------------------------------------------------------


def test_search_by_interest_charges_and_filters() -> None:
    state = fresh_game(LOADED)
    founder = state.founder_of(CID)
    assert founder is not None
    interest = D.interest_keys[0]
    out = apply_action(
        state,
        OpenSearch(founder.id, "software_engineer", "network", interest=interest),
        RngFactory(1),
        B,
        D,
        CASH_,
        seq=0,
    )
    (entry,) = out.ledger_entries
    lines = {line.account: line.amount for line in entry.lines}
    fee = interest_fee_cents("software_engineer", None, B, D)
    assert (
        lines[RECRUITING]
        == fee
        == D.role("software_engineer").salary_band_mid_cents["mid"] * 15 // 100
    )
    state, _ = phases.candidate_batches(out.new_state, RngFactory(1), B, D)
    cands = state.open_candidates(CID)
    assert cands
    for c in cands:
        assert interest in state.person(c.person_id).interests
        reveal = state.reveal(CID, c.person_id)
        assert reveal is not None and reveal.profile_revealed_turn == state.turn


# --- Replace (29.5) -------------------------------------------------------------------------


def _resigned_with_recruiter() -> GameState:
    state = fresh_game(LOADED)
    state = with_employee(
        LOADED, state, make_person(LOADED, 2, "software_engineer", "senior"), 10**7
    )
    state = with_employee(LOADED, state, make_person(LOADED, 3, "recruiter", "mid"), 8 * 10**6)
    e = state.employment_of(2)
    assert e is not None
    return with_employment(
        state, replace(e, status="notice", end_turn=state.turn + 1, end_reason="resigned")
    )


def test_replace_needs_a_recruiter() -> None:
    state = _resigned_with_recruiter()
    assert replace_problem(state, CID, 2, B) is None
    e = state.employment_of(3)
    assert e is not None
    no_recruiter = with_employment(state, replace(e, status="ended", end_reason="resigned"))
    assert "recruiter" in (replace_problem(no_recruiter, CID, 2, B) or "")


def test_replace_offers_in_the_batch_month() -> None:
    state = _resigned_with_recruiter()
    founder = state.founder_of(CID)
    assert founder is not None
    out = apply_action(state, ReplaceLeaver(founder.id, 2), RngFactory(1), B, D, CASH_, seq=0)
    state = out.new_state
    (plan,) = [p for p in state.plans if p.replace_of == 2]
    assert plan.owner_id == 3 and plan.role == "software_engineer" and plan.level == "senior"
    (search,) = [s for s in state.open_searches(CID) if s.plan_id == plan.id]
    assert search.level == "senior" and search.channel == "recruiter"
    state, _ = phases.candidate_batches(state, RngFactory(1), B, D)
    assert all(state.person(c.person_id).level == "senior" for c in state.open_candidates(CID))
    state, _, _ = replace_offers(state, RngFactory(1), B, D, CASH_)
    offers = [o for o in state.pending_offers(CID) if o.plan_id == plan.id]
    assert len(offers) == 1  # offered the month the batch arrived: no month for interviews
    with pytest.raises(Exception):  # noqa: B017 - one replacement at a time
        apply_action(state, ReplaceLeaver(founder.id, 2), RngFactory(1), B, D, CASH_, seq=1)
