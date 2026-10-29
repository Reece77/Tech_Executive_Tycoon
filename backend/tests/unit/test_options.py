"""Options from the pool (formulas.md 14.2): grants on hire, vesting, forfeiture on leaving,
and the retention factor in the resignation chance (formulas.md 10)."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from tests.helpers import (
    fresh_game,
    last_hire,
    make_person,
    mark_interviewed,
    with_candidates,
    with_employee,
)
from tests.unit.test_hiring_phases import Game
from tst.loader import LoadedData
from tst.sim.actions import Fire, MakeOffer
from tst.sim.finance.captable import fd_shares, unallocated
from tst.sim.finance.models import FundingRound
from tst.sim.finance.options import (
    at_cliff,
    grant_on_hire,
    next_vesting,
    retention,
    settle_leavers,
    vest,
)
from tst.sim.hiring.formulas import resignation_bp
from tst.sim.state import with_round


def test_an_accepted_offer_grants_options_from_the_pool(loaded: LoadedData) -> None:
    game = Game(loaded, mark_interviewed(with_candidates(loaded, fresh_game(loaded), 1)))
    (candidate,) = game.state.candidates
    ask = game.state.person(candidate.person_id).salary_expectation_cents or 0
    game.act(MakeOffer(1, candidate.person_id, ask * 3, 50))  # sure to accept
    game.turn()
    (grant,) = game.state.grants
    employment = game.state.employment_of(candidate.person_id)
    assert employment is not None and grant.employment_id == employment.id
    assert (grant.granted, grant.start_turn) == (50_000, 0)  # 50 bp of 10,000,000
    assert unallocated(game.state, 1) == 950_000
    assert fd_shares(game.state, 1) == 10_000_000  # options are inside FD already


def test_vesting_cliff_then_monthly(loaded: LoadedData) -> None:
    state = with_employee(loaded, fresh_game(loaded), make_person(loaded, 2), 9_000_000, 48)
    state = grant_on_hire(state, last_hire(state))
    vested = []
    for turn in range(14):
        state = vest(replace(state, turn=turn), loaded.balance)
        vested.append(state.grants[0].vested)
    assert vested[:11] == [0] * 11
    assert vested[11:] == [12_000, 13_000, 14_000]  # 12, 13 and 14 months served of 48,000


def test_leaving_returns_unvested_options(loaded: LoadedData) -> None:
    state = with_employee(loaded, fresh_game(loaded), make_person(loaded, 2), 9_000_000, 100)
    state = grant_on_hire(state, last_hire(state))
    state = vest(replace(state, turn=23), loaded.balance)  # 24 months: half vested
    assert state.grants[0].vested == 50_000 and unallocated(state, 1) == 900_000
    game = Game(loaded, state)
    game.act(Fire(1, 2))
    (grant,) = game.state.grants
    assert (grant.status, grant.forfeited, grant.outstanding, grant.unvested) == (
        "ended",
        50_000,
        50_000,
        0,
    )
    assert unallocated(game.state, 1) == 950_000
    assert fd_shares(game.state, 1) == 10_000_000
    assert settle_leavers(game.state) == game.state  # settled once


def test_retention_needs_a_share_price(loaded: LoadedData) -> None:
    state = with_employee(loaded, fresh_game(loaded), make_person(loaded, 2), 9_500_000, 75)
    state = grant_on_hire(state, last_hire(state))
    employment = last_hire(state)
    assert retention(state, employment, loaded.balance) == 1.0  # $0 before any priced round
    priced = with_round(
        state,
        FundingRound(
            1,
            1,
            "a",
            "closed",
            1,
            0,
            0,
            closed_turn=0,
            pre_money_cents=896,
            fd_pre=10,
            amount_cents=1,
        ),
    )
    assert priced.funding_round(1) is not None
    assert priced.funding_round(1).price == Fraction(896, 10)  # type: ignore[union-attr]
    factor = retention(priced, employment, loaded.balance)
    assert factor == pytest.approx(0.646, abs=5e-4)  # the 14.10 example
    plain = resignation_bp(25, 6, False, loaded.balance.resign)
    assert resignation_bp(25, 6, False, loaded.balance.resign, retention=factor) == (
        pytest.approx(plain * factor)
    )


def test_next_vesting_is_the_cliff_then_each_month(loaded: LoadedData) -> None:
    """M4b: the profile and cap table show the next vesting date and amount."""
    fb = loaded.balance.finance
    state = with_employee(loaded, fresh_game(loaded), make_person(loaded, 2), 9_000_000, 48)
    state = grant_on_hire(state, last_hire(state))
    (grant,) = state.grants
    assert next_vesting(grant, 0, fb) == (11, 12_000)  # 48 bp: 48,000; the cliff vests 1/4
    assert at_cliff(grant, 11, fb)
    later = replace(grant, vested=12_000)
    assert next_vesting(later, 12, fb) == (12, 1_000) and not at_cliff(later, 12, fb)
    done = replace(grant, vested=grant.granted)
    assert next_vesting(done, 60, fb) is None
    assert next_vesting(replace(grant, status="ended"), 0, fb) is None
