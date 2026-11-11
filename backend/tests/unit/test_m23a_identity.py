"""M23a sub-task 3 (Codex review 5 finding 8; CLAUDE.md 2.2, ADR-0013's stable-identity amendment):
entity-list and appeal draws are keyed by a company's stable key, never its database id. The same
subsidiary founded with and without an unrelated company appended first gets id 41 or 42, the
same stable key, and the same regulatory outcomes."""

from __future__ import annotations

from dataclasses import replace

from tst.balance import m22
from tst.balance.game import start_game
from tst.sim.actions import apply_action
from tst.sim.calendar import ym_to_turn
from tst.sim.geopolitics import listing
from tst.sim.geopolitics.models import Licence
from tst.sim.mining.actions import FoundSubsidiary
from tst.sim.rng import RngFactory
from tst.sim.state import CompanyState, GameState, with_licence, with_person_state

SEEDS = range(1, 201)


def _found(state: GameState, *, unrelated: bool) -> tuple[GameState, int]:
    data = m22.loaded()
    if unrelated:  # an unrelated company first: the subsidiary's id moves up by one
        cid = max(c.id for c in state.companies) + 1
        state = replace(
            state,
            companies=(
                *state.companies,
                CompanyState(id=cid, name="Unrelated Co", is_player=False, stage=1, founded_turn=0),
            ),
        )
    player = state.player
    state = replace(
        state,
        companies=tuple(replace(c, stage=3) if c.id == player.id else c for c in state.companies),
    )
    founder = state.founder_of(player.id)
    assert founder is not None
    ps = state.person_state(founder.id)
    state = with_person_state(state, replace(ps, energy=100))
    out = apply_action(
        state,
        FoundSubsidiary(founder.id, "Grey Chips", "north_america", 100_000_000),
        RngFactory(1),
        data.balance,
        data.game_data,
        {(player.id, "1000_cash"): 10**12},
        seq=1,
    )
    sub = next(c for c in out.new_state.companies if c.name == "Grey Chips")
    return out.new_state, sub.id


def _grey(state: GameState, cid: int) -> GameState:
    return with_licence(
        state, Licence(1, cid, 0, "us_oct_2022", "china", state.turn, state.turn, "grey")
    )


def test_listing_outcomes_do_not_depend_on_an_unrelated_companys_id() -> None:
    data = m22.loaded()
    b, d = data.balance, data.game_data
    base = replace(start_game(data, 6, "funded_spinout").state, turn=ym_to_turn(2022, 10))
    a, sub_a = _found(base, unrelated=False)
    c, sub_c = _found(base, unrelated=True)
    assert sub_a != sub_c
    assert a.company(sub_a).rival_key == c.company(sub_c).rival_key
    a, c = _grey(a, sub_a), _grey(c, sub_c)
    hits_a = {
        s
        for s in SEEDS
        if any(x.company_id == sub_a for x in listing.listing_month(a, RngFactory(s), b, d)[1])
    }
    hits_c = {
        s
        for s in SEEDS
        if any(x.company_id == sub_c for x in listing.listing_month(c, RngFactory(s), b, d)[1])
    }
    assert hits_a and hits_a == hits_c


def test_appeal_draws_do_not_depend_on_an_unrelated_companys_id() -> None:
    data = m22.loaded()
    b = data.balance
    base = replace(start_game(data, 6, "funded_spinout").state, turn=ym_to_turn(2023, 3))
    a, sub_a = _found(base, unrelated=False)
    c, sub_c = _found(base, unrelated=True)
    won_a = [
        listing.appeal_won(replace(a, save_meta=replace(a.save_meta, master_seed=s)), sub_a, b)
        for s in SEEDS
    ]
    won_c = [
        listing.appeal_won(replace(c, save_meta=replace(c.save_meta, master_seed=s)), sub_c, b)
        for s in SEEDS
    ]
    assert any(won_a) and not all(won_a) and won_a == won_c
