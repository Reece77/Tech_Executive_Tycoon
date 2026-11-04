"""M13b sub-task 3 (formulas.md 27.1): executives' pitches. Seeded timing, approval through
the normal actions as the executive (their energy, not the founder's), guardrails, the
Holiday auto-approve limit, a decline's morale, follow-through, and the displayed-knowledge
differential (two executives the company sees identically pitch the same text and numbers)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import with_product
from tests.unit.test_hiring_phases import Game
from tests.unit.test_m10c_executives import EXEC, _company, _give
from tst.loader import LoadedData
from tst.sim.actions.authority import AnswerPitch, SetPitchPolicy
from tst.sim.ledger import CASH
from tst.sim.org import pitches
from tst.sim.org.authority import run_executives
from tst.sim.org.formulas import pitch_chance
from tst.sim.org.models import PitchPolicy
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_pitch_policy

CASH_CENTS = 2_000_000_000  # $20M


def _cpo(loaded: LoadedData, **guards: object) -> GameState:
    state = _company(loaded, "cpo", "product_manager", staff=3)
    state = with_product(state)  # a live B2B SaaS product: the CPO looks elsewhere
    return _give(state, "cpo", loaded.balance, **guards)


def _run(loaded: LoadedData, state: GameState, seed: int, *, at_controls: bool = True):  # type: ignore[no-untyped-def]
    return run_executives(
        state,
        RngFactory(seed),
        loaded.balance,
        loaded.game_data,
        {(1, CASH): CASH_CENTS},
        at_controls=at_controls,
    )


def _pitching_seed(loaded: LoadedData, state: GameState, pitches_: bool = True) -> int:
    """A seed whose quarterly draw makes the executive pitch (or not)."""
    chance = pitch_chance(state.person(EXEC).personality["ambition"], loaded.balance.pitch)
    for seed in range(1, 500):
        u = float(RngFactory(seed).stream(state.turn, "pitch", EXEC).random(2)[0])
        if (u < chance) == pitches_:
            return seed
    raise AssertionError("no seed")


def test_a_cpo_pitches_in_a_quarters_first_month(loaded: LoadedData) -> None:
    state = _cpo(loaded)
    assert pitches.is_draw_month(state.turn)
    seed = _pitching_seed(loaded, state)
    out, _, logs, _ = _run(loaded, state, seed)
    (pitch,) = out.pending_pitches(1)
    assert pitch.seat == "cpo" and pitch.person_id == EXEC and pitch.kind == "new_product"
    assert (
        pitch.low <= pitch.high
        and pitch.cost_cents > 0
        and pitch.hires == loaded.balance.pitch.team_builders
    )
    assert dict(pitch.params)["category"] != "b2b_saas"  # a category it doesn't sell in
    assert any(i.template == "exec_pitch" for i in logs)
    quiet = _pitching_seed(loaded, state, pitches_=False)
    none, _, _, _ = _run(loaded, state, quiet)
    assert none.pending_pitches(1) == ()
    later = replace(state, turn=state.turn + 1)  # not a quarter's first month
    assert _run(loaded, later, seed)[0].pending_pitches(1) == ()


def test_a_pending_pitch_lapses_at_the_next_draw(loaded: LoadedData) -> None:
    state = _cpo(loaded)
    seed = _pitching_seed(loaded, state)
    out, _, _, _ = _run(loaded, state, seed)
    (pitch,) = out.pending_pitches(1)
    nxt = replace(out, turn=out.turn + 3)
    again = _run(loaded, nxt, _pitching_seed(loaded, nxt, pitches_=False))[0]
    assert again.pitch(pitch.id).status == "lapsed"  # type: ignore[union-attr]


def test_approval_runs_the_move_as_the_executive(loaded: LoadedData) -> None:
    """A new product gets a unit, a hiring plan for the suggested team and its price; the
    executive's energy pays, not the founder's (27.1)."""
    state = _cpo(loaded)
    out, _, _, _ = _run(loaded, state, _pitching_seed(loaded, state))
    (pitch,) = out.pending_pitches(1)
    game = Game(loaded, out, cash=CASH_CENTS)
    founder = game.state.founder_of(1).id  # type: ignore[union-attr]
    founder_energy = game.state.person_state(founder).energy
    exec_energy = game.state.person_state(EXEC).energy
    game.act(AnswerPitch(founder, pitch.id, "approve"))
    done = game.state.pitch(pitch.id)
    assert done is not None and done.status == "approved" and done.target_id is not None
    product = game.state.product(done.target_id)
    assert product is not None and product.category == dict(pitch.params)["category"]
    assert product.status == "in_development"
    unit = next(u for u in game.state.active_units(1) if u.product_id == product.id)
    (plan,) = [p for p in game.state.plans if p.unit_id == unit.id]
    assert (plan.target, plan.owner_id) == (loaded.balance.pitch.team_builders, EXEC)
    assert all(s.price_cents for s in game.state.segments_of(product.id))
    assert game.state.person_state(founder).energy == founder_energy
    assert (game.state.person_state(EXEC).energy or 0) < (exec_energy or 100)


def test_guardrails_hold(loaded: LoadedData) -> None:
    """Only the categories the CPO may enter; never a team above the headcount cap."""
    state = _cpo(loaded, categories=("fintech",), headcount_cap=2)
    out, _, _, _ = _run(loaded, state, _pitching_seed(loaded, state))
    (pitch,) = out.pending_pitches(1)
    assert dict(pitch.params)["category"] == "fintech" and pitch.hires == 2
    blocked = _cpo(loaded, headcount_cap=0)
    assert _run(loaded, blocked, _pitching_seed(loaded, blocked))[0].pending_pitches(1) == ()


def test_protected_products_are_not_sunset(loaded: LoadedData) -> None:
    state = _company(loaded, "cpo", "product_manager")
    state = with_product(state, root=False)
    product = state.company_products(1)[0]
    state = replace(
        state,
        turn=12,
        products=tuple(
            replace(p, rotting=True, launched_turn=0) if p.id == product.id else p
            for p in state.products
        ),
    )
    b, d = loaded.balance, loaded.game_data
    open_ = _give(state, "cpo", b, categories=("b2b_saas",))
    kinds = [c.kind for c in pitches.candidates(open_, 1, ("sunset",), CASH_CENTS, b, d)]
    assert kinds == ["sunset"]
    shut = _give(state, "cpo", b, protected_products=(product.id,))
    assert pitches.candidates(shut, 1, ("sunset",), CASH_CENTS, b, d) == []


def test_the_holiday_auto_approve_limit(loaded: LoadedData) -> None:
    """On Holiday a pitch under the limit goes ahead; at 0 every pitch waits; at the controls
    every pitch waits (27.1)."""
    state = _cpo(loaded)
    seed = _pitching_seed(loaded, state)
    away, _, logs, taken = _run(loaded, state, seed, at_controls=False)  # 5% of $20M = $1M
    (pitch,) = away.pitches
    assert pitch.status == "auto_approved" and pitch.cost_cents < CASH_CENTS * 5 // 100
    assert any(i.template == "pitch_went_ahead" for i in logs)
    assert "create_product" in [a.kind for _, a in taken]
    asks = with_pitch_policy(state, PitchPolicy(1, auto_approve_cents=0))
    (waits,) = _run(loaded, asks, seed, at_controls=False)[0].pitches
    assert waits.status == "pending"
    small = with_pitch_policy(state, PitchPolicy(1, auto_approve_cents=pitch.cost_cents))
    assert _run(loaded, small, seed, at_controls=False)[0].pitches[0].status == "pending"
    (here,) = _run(loaded, state, seed, at_controls=True)[0].pitches
    assert here.status == "pending"


def test_a_decline_costs_morale_more_at_high_ego(loaded: LoadedData) -> None:
    for ego, drop in ((10.0, 2.0), (16.0, 4.0)):
        state = _cpo(loaded)
        person = state.person(EXEC)
        person = replace(person, personality=person.personality.updated({"ego": ego}))
        state = replace(state, people=tuple(person if p.id == EXEC else p for p in state.people))
        out, _, _, _ = _run(loaded, state, _pitching_seed(loaded, state))
        (pitch,) = out.pending_pitches(1)
        game = Game(loaded, out, cash=CASH_CENTS)
        before = game.state.person_state(EXEC).morale or 0
        game.act(AnswerPitch(game.state.founder_of(1).id, pitch.id, "decline"))  # type: ignore[union-attr]
        assert game.state.pitch(pitch.id).status == "declined"  # type: ignore[union-attr]
        assert game.state.person_state(EXEC).morale == pytest.approx(before - drop)


def test_pitch_policy_action(loaded: LoadedData) -> None:
    game = Game(loaded, _cpo(loaded))
    founder = game.state.founder_of(1).id  # type: ignore[union-attr]
    game.act(SetPitchPolicy(founder, 1_000_000, True))
    assert game.state.pitch_policy(1) == PitchPolicy(1, 1_000_000, True)


def test_follow_through_scores_after_the_window(loaded: LoadedData) -> None:
    state = _cpo(loaded)
    out, _, _, _ = _run(loaded, state, _pitching_seed(loaded, state), at_controls=False)
    assert len(out.pitches) == 1
    window = loaded.balance.pitch.record_months
    early = pitches.follow_through(
        replace(out, turn=out.turn + window - 1), loaded.balance, loaded.game_data
    )
    assert early.pitches[0].outcome is None
    late = pitches.follow_through(
        replace(out, turn=out.turn + window), loaded.balance, loaded.game_data
    )
    assert late.pitches[0].outcome == "too_early"  # the product never launched
    assert pitches.record(late, EXEC) == (0, 0, 1)


def test_same_displayed_skills_give_the_same_pitch(loaded: LoadedData) -> None:
    """Two CPOs the company sees identically (same displayed ranges, different true skills)
    pitch the same text and numbers when the quality draw picks the same candidate (27.1,
    27.6)."""
    from tst.sim.people.reveal import revealed_range

    state = _cpo(loaded)
    person = state.person(EXEC)
    reveal = state.reveal(1, EXEC)
    assert reveal is not None
    weights = loaded.balance.exec_seats.seats["cpo"].weights
    changed = dict(person.skills.as_dict())
    for skill in weights:
        shown = revealed_range(person, reveal, skill)
        for v in (x / 100 for x in range(100, 2001)):
            alt = replace(person, skills=person.skills.updated({skill: v}))
            if revealed_range(alt, reveal, skill) == shown and abs(v - changed[skill]) > 0.5:
                changed[skill] = v
                break
    other = replace(person, skills=person.skills.updated(changed))
    assert other.skills != person.skills
    twin = replace(state, people=tuple(other if p.id == EXEC else p for p in state.people))
    seed = _pitching_seed(loaded, state)
    a = _run(loaded, state, seed)[0].pending_pitches(1)
    b = _run(loaded, twin, seed)[0].pending_pitches(1)
    assert len(a) == len(b) == 1
    if a[0].params == b[0].params:  # the same candidate: everything shown is the same
        assert a[0] == b[0]
    else:  # the quality draw (true score) picked best and second best
        ranked = pitches.candidates(
            state, 1, ("new_product", "sunset"), CASH_CENTS, loaded.balance, loaded.game_data
        )
        assert {a[0].params, b[0].params} == {tuple(sorted(c.params)) for c in ranked[:2]}


def test_holiday_stops_for_big_pitches_only_when_ticked(loaded: LoadedData) -> None:
    """Above the limit a pitch waits; Holiday stops for it only with "stop for big pitches"
    ticked (27.1)."""
    from tst.holiday import big_pitch_waiting

    state = _cpo(loaded)
    tiny = with_pitch_policy(state, PitchPolicy(1, auto_approve_cents=1))
    out, _, _, _ = _run(loaded, tiny, _pitching_seed(loaded, state), at_controls=False)
    (pitch,) = out.pending_pitches(1)  # above a $0.01 limit: it waits
    assert not big_pitch_waiting(out, CASH_CENTS, loaded.balance)
    ticked = with_pitch_policy(out, PitchPolicy(1, auto_approve_cents=1, stop_for_big=True))
    assert big_pitch_waiting(ticked, CASH_CENTS, loaded.balance)
    roomy = with_pitch_policy(
        out, PitchPolicy(1, auto_approve_cents=pitch.cost_cents + 1, stop_for_big=True)
    )
    assert not big_pitch_waiting(roomy, CASH_CENTS, loaded.balance)


def test_the_ceo_pitches_across_the_functions_it_runs(loaded: LoadedData) -> None:
    """A CEO with no seat holder covering a function pitches that function's moves (27.1);
    at the controls the pitch waits for the Chair."""
    from tests.unit.test_m13_ceo import CEO, staffed, with_ceo_appointed
    from tst.sim.org.ceo import run_ceo

    state = with_ceo_appointed(staffed())
    state = replace(state, turn=state.turn - state.turn % 3)  # a quarter's first month
    chance = pitch_chance(state.person(CEO).personality["ambition"], loaded.balance.pitch)
    seed = next(
        s
        for s in range(1, 500)
        if float(RngFactory(s).stream(state.turn, "pitch", CEO).random()) < chance
    )
    out, _, _, taken = run_ceo(
        state,
        RngFactory(seed),
        loaded.balance,
        loaded.game_data,
        {(1, CASH): 10**12},
        at_controls=True,
    )
    mine = [p for p in out.pending_pitches(1) if p.person_id == CEO]
    if mine:
        (pitch,) = mine
        assert pitch.seat == "ceo"
        assert pitch.kind in {k for kinds in pitches.SEAT_KINDS.values() for k in kinds}
        assert not any(a.kind in ("create_product", "build_facility") for _, a in taken)
    else:  # no candidate in any function this month: nothing pending, nothing done
        assert out.pending_pitches(1) == ()


def test_a_hit_reaches_the_central_case(loaded: LoadedData) -> None:
    """Scored against the central case from displayed estimates, the same for every
    executive, not its own low case (product manager's ruling, 2026-11-04)."""
    from tst.sim.research.models import ResearchLead

    state = _cpo(loaded)
    out, _, _, _ = _run(loaded, state, _pitching_seed(loaded, state), at_controls=False)
    (pitch,) = out.pitches
    assert pitch.low < pitch.central < pitch.high
    research = replace(
        pitch, kind="research", params=(("domain", "ai"),), baseline=0, low=2, central=10
    )
    later = replace(out, turn=out.turn + loaded.balance.pitch.record_months, pitches=(research,))
    for lead, outcome in ((10.0, "hit"), (9.0, "miss")):  # 9 is above the low case: a miss
        at = replace(later, research_leads=(ResearchLead(1, "ai", lead),))
        scored = pitches.follow_through(at, loaded.balance, loaded.game_data)
        assert scored.pitches[0].outcome == outcome


def test_execution_follows_the_executives_seat_factor(loaded: LoadedData) -> None:
    """A new product's team pace and a region's sales ramp follow the executing executive's
    true seat factor (18.3) for the record window; the API's estimate uses the displayed
    score (product manager's ruling, 2026-11-04)."""
    from tst.sim.org.executives import true_score
    from tst.sim.org.formulas import seat_effect, seat_multiplier
    from tst.sim.org.pitch_execution import execution_factor

    state = _cpo(loaded)
    out, _, _, _ = _run(loaded, state, _pitching_seed(loaded, state), at_controls=False)
    (pitch,) = out.pitches
    b = loaded.balance
    expected = seat_multiplier(
        seat_effect(true_score(out, EXEC, "cpo", b), b.exec_seats), b.exec_seats.seats["cpo"].effect
    )
    product = pitch.target_id
    assert product is not None
    assert execution_factor(out, "new_product", product, b) == pytest.approx(expected)
    assert execution_factor(out, "new_product", product + 1, b) == 1.0
    assert execution_factor(out, "region", product, b, "europe") == 1.0
    late = replace(out, turn=out.turn + b.pitch.record_months)
    assert execution_factor(late, "new_product", product, b) == 1.0
    shown = execution_factor(out, "new_product", product, b, estimate=True)
    assert shown > 0
