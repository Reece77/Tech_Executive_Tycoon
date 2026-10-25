"""M2a offer changes: interview before offer (ADR-0016), the pitch term (formulas.md 7), and
the M1 expiry fix (a pending offer keeps its candidate until it resolves)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, make_person, with_candidates, with_employee
from tests.unit.test_hiring_phases import Game
from tst.loader import LoadedData
from tst.sim.actions import CreatePlan, Interview, MakeOffer, OpenSearch, ReferenceCheck
from tst.sim.errors import InterviewRequired
from tst.sim.hiring.formulas import offer_score
from tst.sim.hiring.phases import resolve_offers
from tst.sim.hiring.rules import offer_pitch, offer_preview
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_person

FOUNDER = 1
DELEGATE = 2


def staffed(loaded: LoadedData, candidates: int = 2) -> Game:
    state = with_employee(loaded, fresh_game(loaded), make_person(loaded, DELEGATE), 9_000_000)
    state = replace(state, next_ids=replace(state.next_ids, person=3))
    return Game(loaded, with_candidates(loaded, state, candidates))


def test_player_offer_needs_an_interview(loaded: LoadedData) -> None:
    game = staffed(loaded)
    with pytest.raises(InterviewRequired, match="interview candidate 3"):
        game.act(MakeOffer(FOUNDER, 3, 9_000_000, 0))
    game.act(ReferenceCheck(FOUNDER, 3))  # a reference check is not an interview
    with pytest.raises(InterviewRequired):
        game.act(MakeOffer(FOUNDER, 3, 9_000_000, 0))
    game.act(Interview(FOUNDER, 3))
    assert game.state.candidate(3).interviewed_turn == 0  # type: ignore[union-attr]
    game.act(MakeOffer(FOUNDER, 3, 9_000_000, 0))
    assert game.state.pending_offer_for(3) is not None


def test_delegate_offer_needs_an_interview_and_a_delegate_interview_counts(
    loaded: LoadedData,
) -> None:
    game = staffed(loaded)
    game.act(CreatePlan(FOUNDER, DELEGATE, "software_engineer", 1, "network", 10_000))
    with pytest.raises(InterviewRequired):
        game.act(MakeOffer(DELEGATE, 3, 9_000_000, 0, plan_id=1))
    game.act(Interview(DELEGATE, 3))  # the delegate interviews for the company
    game.act(MakeOffer(FOUNDER, 3, 9_000_000, 0))
    offer = game.state.pending_offer_for(3)
    assert offer is not None and offer.actor_id == FOUNDER


def test_network_candidates_still_need_an_interview(loaded: LoadedData) -> None:
    game = Game(loaded, fresh_game(loaded))
    game.act(OpenSearch(FOUNDER, "designer", "network"))
    game.turn()
    candidate = game.state.candidates[0]
    assert game.state.reveal(1, candidate.person_id).profile_revealed_turn is not None  # type: ignore[union-attr]
    with pytest.raises(InterviewRequired):
        game.act(MakeOffer(FOUNDER, candidate.person_id, 9_000_000, 0))


# --- Pitch ----------------------------------------------------------------------------------


def test_founder_pitch_uses_true_recruiting(loaded: LoadedData) -> None:
    state = fresh_game(loaded)  # engineer default: recruiting 7
    assert offer_pitch(state, FOUNDER, loaded.balance.hiring) == pytest.approx(-0.09)


def test_offer_score_adds_the_pitch(loaded: LoadedData) -> None:
    kwargs = {
        "ratio": 1.0,
        "equity_bp": 50,
        "matching_interests": 1,
        "risk_appetite": 10.0,
        "ambition": 10.0,
        "stage": 0,
        "offer": loaded.balance.hiring.offer,
    }
    assert offer_score(**kwargs, pitch=0.15) == pytest.approx(offer_score(**kwargs) + 0.15)  # type: ignore[arg-type]


def _with_recruiting(state: GameState, person_id: int, value: float) -> GameState:
    person = state.person(person_id)
    return with_person(state, replace(person, skills=person.skills.updated({"recruiting": value})))


def test_resolution_uses_the_offer_makers_recruiting(loaded: LoadedData) -> None:
    """Same offers and draws; a recruiting-20 maker lands more than a recruiting-1 maker."""
    game = staffed(loaded, candidates=1)
    game.act(Interview(FOUNDER, 3))
    ask = game.state.person(3).salary_expectation_cents or 0
    game.act(MakeOffer(FOUNDER, 3, ask, 0))
    accepted = {}
    for recruiting in (1.0, 20.0):
        state = _with_recruiting(game.state, FOUNDER, recruiting)
        count = 0
        for seed in range(400):
            resolved, _, _ = resolve_offers(
                state, RngFactory(seed), loaded.balance, loaded.game_data
            )
            count += resolved.offer(1).status == "accepted"  # type: ignore[union-attr]
        accepted[recruiting] = count
    assert accepted[20.0] > accepted[1.0]


def test_offer_preview_includes_the_pitch(loaded: LoadedData) -> None:
    state = with_candidates(loaded, fresh_game(loaded), 1)
    candidate = state.candidates[0]
    ask = state.person(candidate.person_id).salary_expectation_cents or 0
    high = _with_recruiting(state, FOUNDER, 20)
    rank = {"unlikely": 0, "uncertain": 1, "likely": 2}
    gains = []
    for pct in range(90, 131, 2):
        salary = ask * pct // 100
        plain = offer_preview(state, candidate, salary, 0, loaded.balance, loaded.game_data)
        pitched = offer_preview(
            high, candidate, salary, 0, loaded.balance, loaded.game_data, FOUNDER
        )
        gains.append(rank[pitched.hint] - rank[plain.hint])
    assert min(gains) >= 0 and max(gains) > 0  # +0.3 pitch never hurts, and moves a band


# --- Expiry fix -----------------------------------------------------------------------------


def test_offer_made_in_a_candidates_last_month_still_resolves(loaded: LoadedData) -> None:
    game = staffed(loaded, candidates=2)
    game.state = replace(
        game.state, candidates=tuple(replace(c, expires_turn=0) for c in game.state.candidates)
    )
    game.act(Interview(FOUNDER, 3))
    ask = game.state.person(3).salary_expectation_cents or 0
    game.act(MakeOffer(FOUNDER, 3, round(ask * 1.5), 0))
    result = game.turn()
    statuses = {c.person_id: c.status for c in result.new_state.candidates}
    assert statuses[3] in ("hired", "declined")  # resolved in phase 1, not expired
    assert statuses[4] == "expired"  # no offer: leaves in phase 12 of its last month
    assert result.new_state.offer(1).status in ("accepted", "declined")  # type: ignore[union-attr]


def test_delegate_offer_in_the_last_month_blocks_expiry_until_it_resolves(
    loaded: LoadedData,
) -> None:
    game = staffed(loaded, candidates=1)
    game.state = replace(
        game.state, candidates=tuple(replace(c, expires_turn=0) for c in game.state.candidates)
    )
    game.act(CreatePlan(FOUNDER, DELEGATE, "software_engineer", 1, "network", 12_000))
    first = game.turn()  # phase 2: interview and offer; phase 12: the offer keeps them
    assert any(isinstance(a, MakeOffer) for _, a in first.delegate_actions)
    assert game.state.candidate(3) is not None
    assert game.state.candidate(3).status == "open"  # type: ignore[union-attr]
    second = game.turn()  # phase 1 of the next turn answers
    assert {c.person_id: c.status for c in second.new_state.candidates}[3] in (
        "hired",
        "declined",
    )
