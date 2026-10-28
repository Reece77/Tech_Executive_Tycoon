"""Hiring actions (ADR-0014): immediate, pure, and all-or-nothing."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, make_person, with_candidates, with_employee
from tst.loader import LoadedData
from tst.sim.actions import (
    CloseSearch,
    Fire,
    Interview,
    MakeOffer,
    OpenSearch,
    ReferenceCheck,
    WithdrawOffer,
    action_from_payload,
    action_payload,
    apply_action,
)
from tst.sim.errors import (
    InsufficientCashError,
    InsufficientEnergyError,
    InvalidActionError,
    OfferExistsError,
    OptionPoolError,
    UnknownCandidateError,
    UnknownOfferError,
    UnknownRoleError,
    UnknownSearchError,
)
from tst.sim.finance.captable import unallocated
from tst.sim.finance.options import grant_on_hire
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH
from tst.sim.people.models import PA_KEY
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_person_state, with_reveal

RICH = {(1, CASH): 40_000_000}


def act(loaded: LoadedData, state: GameState, action: object, seq: int = 1, balances=RICH):  # type: ignore[no-untyped-def]
    return apply_action(
        state,
        action,  # type: ignore[arg-type]
        RngFactory(state.save_meta.master_seed),
        loaded.balance,
        loaded.game_data,
        balances,
        seq=seq,
    )


def energy(state: GameState) -> int | None:
    return state.person_state(1).energy


@pytest.mark.parametrize(("channel", "cost"), [("network", 10), ("job_post", 5), ("recruiter", 5)])
def test_open_search_spends_energy(loaded: LoadedData, channel: str, cost: int) -> None:
    state = fresh_game(loaded)
    out = act(loaded, state, OpenSearch(1, "designer", channel))  # type: ignore[arg-type]
    (search,) = out.new_state.searches
    assert (search.id, search.role, search.channel, search.status) == (
        1,
        "designer",
        channel,
        "open",
    )
    assert energy(out.new_state) == 60 - cost
    assert out.new_state.next_ids.search == 2
    assert energy(state) == 60  # input untouched


def test_open_search_errors(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    with pytest.raises(UnknownRoleError):
        act(loaded, state, OpenSearch(1, "astronaut", "network"))
    with pytest.raises(InvalidActionError):
        act(loaded, state, OpenSearch(1, "designer", "carrier_pigeon"))  # type: ignore[arg-type]
    with pytest.raises(InsufficientCashError):
        act(loaded, state, OpenSearch(1, "designer", "job_post"), balances={(1, CASH): 49_999})
    act(loaded, state, OpenSearch(1, "designer", "job_post"), balances={(1, CASH): 50_000})
    tired = with_person_state(state, PersonState(person_id=1, energy=9))
    with pytest.raises(InsufficientEnergyError, match="network needs 10 energy; 9 left"):
        act(loaded, tired, OpenSearch(1, "designer", "network"))


def test_close_search(loaded: LoadedData) -> None:
    state = act(loaded, fresh_game(loaded), OpenSearch(1, "designer", "job_post")).new_state
    closed = act(loaded, state, CloseSearch(1, 1)).new_state
    assert closed.searches[0].status == "closed"
    assert closed.searches[0].closed_turn == 0
    with pytest.raises(UnknownSearchError):
        act(loaded, closed, CloseSearch(1, 1))


def test_interview_narrows_and_reveals_profile(loaded: LoadedData) -> None:
    state = with_candidates(loaded, fresh_game(loaded), 2)
    before = state.reveal(1, 2)
    assert before is not None and before.profile_revealed_turn is None
    out = act(loaded, state, Interview(1, 2))
    after = out.new_state.reveal(1, 2)
    assert after is not None
    assert after.record("software_engineering").hw < before.record("software_engineering").hw
    assert after.record("ambition").hw < before.record("ambition").hw
    assert after.record(PA_KEY).hw < before.record(PA_KEY).hw
    assert after.profile_revealed_turn == 0
    assert energy(out.new_state) == 52
    # The other candidate is untouched.
    assert out.new_state.reveal(1, 3) == state.reveal(1, 3)


def test_reference_check_narrows_personality_and_pa_only(loaded: LoadedData) -> None:
    state = with_candidates(loaded, fresh_game(loaded), 1)
    before = state.reveal(1, 2)
    after = act(loaded, state, ReferenceCheck(1, 2)).new_state.reveal(1, 2)
    assert before is not None and after is not None
    assert after.record("software_engineering") == before.record("software_engineering")
    assert after.record("ambition").hw < before.record("ambition").hw
    assert after.profile_revealed_turn is None


def test_checks_roll_hidden_tags_from_the_actions_stream(loaded: LoadedData) -> None:
    """Over many seeds, a check reveals each hidden tag about 15% of the time, seeded by seq."""
    state = with_candidates(loaded, fresh_game(loaded), 1)
    person = state.person(2)
    tagged = replace(person, tags=("mentor", "maverick"))
    state = replace(state, people=(state.people[0], tagged))
    revealed = 0
    for seq in range(1, 401):
        out = act(loaded, state, Interview(1, 2), seq=seq)
        reveal = out.new_state.reveal(1, 2)
        assert reveal is not None
        revealed += len(reveal.revealed_tags)
        assert len(out.log_items) == len(reveal.revealed_tags)
        assert all(i.template == "tag_revealed" for i in out.log_items)
    assert 0.11 <= revealed / 800 <= 0.19
    # Same seq, same result.
    assert act(loaded, state, Interview(1, 2), seq=7) == act(loaded, state, Interview(1, 2), seq=7)


def test_checks_need_an_open_candidate(loaded: LoadedData) -> None:
    state = with_candidates(loaded, fresh_game(loaded), 1)
    with pytest.raises(UnknownCandidateError):
        act(loaded, state, Interview(1, 99))
    with pytest.raises(UnknownCandidateError):
        act(loaded, state, ReferenceCheck(1, 1))  # the founder is not a candidate


def test_offers_withdraw_and_remake(loaded: LoadedData) -> None:
    state = with_candidates(loaded, fresh_game(loaded), 1, interviewed=True)
    offered = act(loaded, state, MakeOffer(1, 2, 9_000_000, 50)).new_state
    (offer,) = offered.offers
    assert (offer.id, offer.candidate_id, offer.status, offer.made_turn) == (1, 2, "pending", 0)
    assert energy(offered) == 60  # offers cost 0 energy
    with pytest.raises(OfferExistsError):
        act(loaded, offered, MakeOffer(1, 2, 9_500_000, 50))
    withdrawn = act(loaded, offered, WithdrawOffer(1, 1)).new_state
    assert withdrawn.offer(1) is not None and withdrawn.offer(1).status == "withdrawn"  # type: ignore[union-attr]
    candidate = withdrawn.candidate(2)
    assert candidate is not None and candidate.status == "open"  # the candidate stays
    remade = act(loaded, withdrawn, MakeOffer(1, 2, 9_500_000, 50)).new_state
    assert remade.pending_offer_for(2) is not None
    assert remade.pending_offer_for(2).id == 2  # type: ignore[union-attr]
    with pytest.raises(UnknownOfferError):
        act(loaded, remade, WithdrawOffer(1, 1))
    with pytest.raises(InvalidActionError):
        act(loaded, state, MakeOffer(1, 2, 0, 0))


def test_option_pool_and_per_offer_cap(loaded: LoadedData) -> None:
    state = with_candidates(loaded, fresh_game(loaded), 6, interviewed=True)
    with pytest.raises(OptionPoolError, match="at most 200 bp"):
        act(loaded, state, MakeOffer(1, 2, 9_000_000, 201))
    # M4 (14.2): an employee's 300 bp is a grant of 300,000 options out of the 1,000,000 pool;
    # pending offers may not exceed the 700,000 left.
    state = with_employee(loaded, state, make_person(loaded, 50), 9_000_000, equity_bp=300)
    state = grant_on_hire(state, state.employments[-1])
    assert unallocated(state, 1) == 700_000
    for i, pid in enumerate((2, 3, 4)):
        state = act(loaded, state, MakeOffer(1, pid, 9_000_000, 200), seq=i + 1).new_state
    # 600,000 options promised: 100,000 left.
    with pytest.raises(OptionPoolError, match="100,000 unallocated options left"):
        act(loaded, state, MakeOffer(1, 5, 9_000_000, 101))
    state = act(loaded, state, MakeOffer(1, 5, 9_000_000, 100)).new_state
    with pytest.raises(OptionPoolError, match=" 0 unallocated options left"):
        act(loaded, state, MakeOffer(1, 6, 9_000_000, 1))


def test_fire(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    state = with_employee(loaded, state, make_person(loaded, 20), 11_500_000, morale=60)
    stays = replace(make_person(loaded, 21), tags=())
    state = with_employee(loaded, state, stays, 9_000_000, morale=60)
    out = act(loaded, state, Fire(1, 20))
    employment = next(e for e in out.new_state.employments if e.person_id == 20)
    assert (employment.status, employment.end_turn, employment.end_reason) == ("ended", 0, "fired")
    (entry,) = out.ledger_entries
    assert {(ln.account, ln.amount) for ln in entry.lines} == {
        ("6000_salaries", 958_333),
        (CASH, -958_333),
    }
    assert out.new_state.person_state(21).morale == 57  # -3
    assert out.new_state.person_state(1).morale is None  # the founder has no morale
    assert [i.template for i in out.log_items] == ["fired"]
    assert dict(out.log_items[0].params)["severance_cents"] == 958_333


def test_firing_a_culture_carrier_costs_six(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    carrier = replace(make_person(loaded, 20), tags=("culture_carrier",))
    state = with_employee(loaded, state, carrier, 9_000_000)
    state = with_employee(loaded, state, make_person(loaded, 21), 9_000_000, morale=4)
    out = act(loaded, state, Fire(1, 20))
    assert out.new_state.person_state(21).morale == 0  # 4 - 6, clamped


def test_firing_a_culture_carrier_reveals_the_tag(loaded: LoadedData) -> None:
    """The bigger morale hit gives the tag away: the company learns it, with an inbox item."""
    state = fresh_game(loaded)
    carrier = replace(make_person(loaded, 20), tags=("mentor", "culture_carrier"))
    state = with_employee(loaded, state, carrier, 9_000_000)
    out = act(loaded, state, Fire(1, 20))
    reveal = out.new_state.reveal(1, 20)
    assert reveal is not None and reveal.revealed_tags == (("culture_carrier", 0),)
    assert [i.template for i in out.log_items] == ["fired", "culture_carrier_left"]
    left = out.log_items[1]
    assert (left.link_kind, left.link_id) == ("person", 20)

    # Already noticed: no second announcement.
    noticed = with_reveal(
        state, replace(state.reveal(1, 20), revealed_tags=(("culture_carrier", 0),))
    )  # type: ignore[arg-type]
    again = act(loaded, noticed, Fire(1, 20))
    assert [i.template for i in again.log_items] == ["fired"]

    # Anyone else: no reveal, no extra item.
    plain = with_employee(loaded, fresh_game(loaded), replace(make_person(loaded, 30), tags=()), 1)
    assert [i.template for i in act(loaded, plain, Fire(1, 30)).log_items] == ["fired"]


def test_cannot_fire_founder_or_strangers(loaded: LoadedData) -> None:
    state = with_candidates(loaded, fresh_game(loaded), 1)
    with pytest.raises(InvalidActionError, match="founder"):
        act(loaded, state, Fire(1, 1))
    with pytest.raises(Exception, match="not on staff"):
        act(loaded, state, Fire(1, 2))


@pytest.mark.parametrize(
    "action",
    [
        OpenSearch(1, "designer", "network"),
        CloseSearch(1, 4),
        Interview(1, 2),
        ReferenceCheck(1, 2),
        MakeOffer(1, 2, 9_000_000, 25),
        WithdrawOffer(1, 3),
        Fire(1, 5),
    ],
)
def test_payload_round_trip(action: object) -> None:
    payload = action_payload(action)  # type: ignore[arg-type]
    assert payload["kind"] == action.kind  # type: ignore[attr-defined]
    assert action_from_payload(payload) == action
