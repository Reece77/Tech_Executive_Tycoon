"""M48 sub-tasks 2-4 (docs/formulas.md 59.1-59.3): agendas from the engine's facts, seeded
hidden priorities, the closed move sets and their checks, bounded effects, commitments tracked
as promises (kept lifts confidence, broken costs double), guidance on a call, credibility
halving gains, investor days, skip, and the outcome action's own bounds."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.test_m13_public import CID, LOADED, MRR, OP, _report, ipo_history, listed
from tst.sim.actions import apply_action
from tst.sim.errors import MeetingRuleError
from tst.sim.ledger import CASH
from tst.sim.meetings import agenda, engine
from tst.sim.meetings.actions import MeetingOutcome, outcome_action
from tst.sim.meetings.config import ALL_MOVES, MOVES, TOPICS
from tst.sim.meetings.models import Meeting, Move
from tst.sim.press import promises
from tst.sim.press.moments import adjust_credibility, credibility
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, guidance_for, public_of, with_company

B = LOADED.balance
MB = B.meetings
CASH_CENTS = 10**10
RICH = {(CID, CASH): 10**14}


def after_report() -> GameState:
    """A listed company at the quarter start after a report (an earnings call is due)."""
    return _report(listed(), MRR * 3, MRR * 3)


def _open(state: GameState, kind: str, plan: object = None) -> Meeting:
    return agenda.open_meeting(
        state,
        kind,  # type: ignore[arg-type]
        RngFactory(state.save_meta.master_seed),
        B,
        LOADED.game_data,
        CASH_CENTS,
        plan,  # type: ignore[arg-type]
    )


def _play(m: Meeting, *moves: Move) -> Meeting:
    while m.status == "open":
        m = engine.play_item(m, moves, MB)
    return m


def _apply(state: GameState, action: object) -> GameState:
    out = apply_action(
        state,
        action,  # type: ignore[arg-type]
        RngFactory(state.save_meta.master_seed),
        B,
        LOADED.game_data,
        RICH,
        seq=1,
    )
    return out.new_state


def _founder(state: GameState) -> int:
    f = state.founder_of(CID)
    assert f is not None
    return f.id


def test_when_meetings_are_held() -> None:
    state = after_report()
    assert agenda.problem(state, "board", B) is None
    assert agenda.problem(state, "call", B) is None
    later = replace(state, turn=state.turn + 1)
    assert agenda.problem(later, "board", B) is not None
    assert agenda.problem(later, "call", B) is not None
    with pytest.raises(MeetingRuleError):
        _open(later, "call")


def test_agendas_come_from_displayed_facts_and_draws_are_seeded() -> None:
    state = after_report()
    board = _open(state, "board")
    assert [i.title for i in board.items][:3] == [
        "Results against plan",
        "Next quarter's plan",
        "Cash and runway",
    ]
    assert board.items[1].figure is not None  # the plan figure a commitment is made to
    assert all(s.kind == "director" and s.seat_id is not None for s in board.speakers)
    for w in board.hidden.priorities:
        assert len(w) == len(TOPICS) and abs(sum(w) - 1) < 1e-9
    assert _open(state, "board") == board  # same seed, same meeting
    other = replace(state, save_meta=replace(state.save_meta, master_seed=999))
    assert _open(other, "board").hidden.priorities != board.hidden.priorities
    call = _open(state, "call")
    assert call.items[0].guidance and call.guidance_base is not None
    assert all(s.kind == "analyst" for s in call.speakers)


def test_moves_outside_the_kind_or_unsupported_become_neutral() -> None:
    state = after_report()
    board = _open(state, "board")
    first = board.items[0]  # no figure: a commit is neutral; a bad fact index is neutral
    checked = engine.check_moves(
        board, first, (Move("commit"), Move("explain", 99), Move("raise")), MB.max_moves
    )
    assert [m.kind for m in checked] == ["neutral", "neutral", "neutral"][: len(checked)]
    plan = board.items[1]
    ok = engine.check_moves(board, plan, (Move("commit"), Move("explain", 0)), MB.max_moves)
    assert [m.kind for m in ok] == ["commit", "explain"]
    call = _open(state, "call")
    g = engine.check_moves(call, call.items[0], (Move("raise"), Move("lower")), MB.max_moves)
    assert [m.kind for m in g] == ["raise"]  # one guidance move an answer


@settings(max_examples=40, deadline=None)
@given(st.lists(st.lists(st.sampled_from(ALL_MOVES), min_size=1, max_size=4), min_size=5))
def test_effects_never_exceed_their_bounds(answers: list[list[str]]) -> None:
    state = _STATE
    for kind in ("board", "call"):
        m = _open(state, kind)
        i = 0
        while m.status == "open":
            m = engine.play_item(m, tuple(Move(k, 0) for k in answers[i % len(answers)]), MB)
            i += 1
        e = m.effects
        assert e is not None
        assert all(abs(d) <= MB.board.step + 1e-9 for _s, d in e.confidence)
        assert abs(e.sentiment) <= MB.call.step + 1e-9
        assert all(abs(t) <= MB.call.target_step + 1e-9 for _i, t in e.targets)
        assert all(a.moves and all(x.kind in MOVES[kind] for x in a.moves) for a in m.answers)
        # the action accepts what the engine computed
        _apply(state, outcome_action(m, _founder(state)))


_STATE = after_report()


def test_good_answers_lift_and_bad_ones_cost() -> None:
    state = after_report()
    good = _play(_open(state, "board"), Move("commit"), Move("explain", 0)).effects
    bad = _play(_open(state, "board"), Move("defer"), Move("push_back")).effects
    assert good is not None and bad is not None
    assert all(d > 0 for _s, d in good.confidence)
    assert all(d < 0 for _s, d in bad.confidence)
    skip = engine.skip(_open(state, "board"))
    assert skip.status == "skipped" and skip.effects is None


def test_a_better_communicator_moves_more() -> None:
    state = after_report()
    m = _open(state, "board")
    strong = replace(m, hidden=replace(m.hidden, skill=MB.skill.band.hi))
    weak = replace(m, hidden=replace(m.hidden, skill=MB.skill.band.lo))
    moves = (Move("explain", 0),)
    up = _play(strong, *moves).effects
    down = _play(weak, *moves).effects
    assert up is not None and down is not None
    assert sum(d for _s, d in up.confidence) > sum(d for _s, d in down.confidence)


def test_the_board_outcome_moves_confidence_and_tracks_the_commitment() -> None:
    state = after_report()
    m = _play(_open(state, "board"), Move("commit"), Move("explain", 0))
    action = outcome_action(m, _founder(state))
    before = {s.id: s.confidence for s in state.board(CID)}
    after = _apply(state, action)
    for seat_id, d in action.confidence:
        assert after.board(CID) and next(
            s for s in after.board(CID) if s.id == seat_id
        ).confidence == pytest.approx(min(100.0, (before[int(seat_id)] or 0) + d))
    made = [p for p in after.promises if p.kind == "commitment"]
    assert len(made) == 1 and made[0].deadline_turn == state.turn + 2
    assert made[0].domain == "revenue" and made[0].level == m.items[1].figure.value  # type: ignore[union-attr]
    # the founder's energy paid for the meeting
    fid = _founder(state)
    assert after.person_state(fid).energy == (state.person_state(fid).energy or 0) - MB.energy[
        "board"
    ]


def _at_deadline(state: GameState, mult: float) -> GameState:
    """The commitment's quarter played at `mult` x the committed revenue: the deadline month's
    phase 12 (the quarter's last month)."""
    level = next(p.level for p in state.promises if p.level is not None)
    revenue = round(level * mult / 3)
    state = replace(state, turn=state.turn + 2)
    for _ in range(3):
        state = ipo_history(state, state.player, revenue, OP)
    return state


@pytest.mark.parametrize(("revenue_mult", "kept"), [(1.1, True), (0.9, False)])
def test_a_commitment_kept_lifts_and_broken_costs_double(revenue_mult: float, kept: bool) -> None:
    state = after_report()
    m = _play(_open(state, "board"), Move("commit"))
    state = _apply(state, outcome_action(m, _founder(state)))
    before = {s.id: s.confidence for s in state.board(CID) if s.confidence is not None}
    state = _at_deadline(state, revenue_mult)
    state, logs = promises.check(state, RngFactory(1), B, LOADED.game_data)
    p = next(p for p in state.promises if p.kind == "commitment")
    assert p.status == ("kept" if kept else "broken")
    want = MB.board.commitment_kept * (1 if kept else -MB.board.commitment_broken_mult)
    for s in state.board(CID):
        if s.id in before:
            assert s.confidence == pytest.approx(max(0.0, min(100.0, before[s.id] + want)))
    assert any(log.template == f"commitment_{'kept' if kept else 'broken'}" for log in logs)


def test_a_call_sets_guidance_and_moves_the_market() -> None:
    state = after_report()
    m = _play(_open(state, "call"), Move("raise"), Move("explain", 0))
    action = outcome_action(m, _founder(state))
    assert action.guidance is not None
    base = m.guidance_base
    assert base is not None
    assert action.guidance[0] == round(base[0] * (1 + MB.call.guidance_step))
    before = public_of(state, CID)
    after = _apply(state, action)
    g = guidance_for(after, CID, state.turn)
    assert g is not None and g.by_player and g.revenue_cents == action.guidance[0]
    pub = public_of(after, CID)
    assert pub is not None and before is not None
    assert pub.sentiment == pytest.approx(before.sentiment * (1 + action.sentiment))
    assert any(p.kind == "guidance" for p in after.promises)


@pytest.mark.parametrize(("revenue_mult", "kept"), [(1.1, True), (0.9, False)])
def test_guidance_kept_or_broken_moves_credibility(revenue_mult: float, kept: bool) -> None:
    state = after_report()
    m = _play(_open(state, "call"), Move("reaffirm"))
    state = _apply(state, outcome_action(m, _founder(state)))
    cred = credibility(state, CID, B)
    state = _at_deadline(state, revenue_mult)
    state, _ = promises.check(state, RngFactory(1), B, LOADED.game_data)
    want = MB.credibility.guidance_kept if kept else -MB.credibility.guidance_broken
    assert credibility(state, CID, B) == pytest.approx(cred + want)


def test_deflecting_a_real_problem_costs_credibility() -> None:
    state = after_report()
    m = _open(state, "call")
    m = replace(m, items=tuple(replace(i, problem=True) for i in m.items))
    done = _play(m, Move("deflect"))
    assert done.effects is not None
    assert done.effects.credibility == pytest.approx(-MB.call.deflect_cred * len(m.items))


def test_low_credibility_halves_gains() -> None:
    state = after_report()
    m = _open(state, "call")
    full = _play(replace(m, credibility=MB.credibility.full_at), Move("explain", 0)).effects
    low = _play(replace(m, credibility=MB.credibility.half_at), Move("explain", 0)).effects
    assert full is not None and low is not None
    if full.sentiment < MB.call.step:  # unclamped: exactly half
        assert low.sentiment == pytest.approx(full.sentiment / 2)
    else:
        assert low.sentiment <= full.sentiment / 2 + 1e-9 or low.sentiment < full.sentiment


def test_an_investor_day_scores_its_plan() -> None:
    state = after_report()
    good = agenda.plan_for("new_industry", "Entering robotics", ("ROC 25%",), 0.25, MB)
    poor = agenda.plan_for("new_industry", "Entering robotics", ("ROC -5%",), -0.05, MB)
    assert good.economics == 1.0 and poor.economics < 0
    e_good = _play(_open(state, "investor_day", good), Move("explain", 0)).effects
    e_poor = _play(_open(state, "investor_day", poor), Move("explain", 0)).effects
    assert e_good is not None and e_poor is not None
    assert e_good.sentiment > e_poor.sentiment
    assert abs(e_good.sentiment) <= MB.investor_day.step + 1e-9
    assert abs(e_good.credibility) <= MB.investor_day.cred_step + 1e-9
    with pytest.raises(MeetingRuleError):
        _open(state, "investor_day")  # a plan is needed


def test_the_action_rechecks_its_bounds() -> None:
    state = after_report()
    fid = _founder(state)
    seat = next(s for s in state.board(CID) if s.confidence is not None)
    too_much = MeetingOutcome(fid, "board", state.turn, confidence=((seat.id, MB.board.step + 1),))
    with pytest.raises(MeetingRuleError):
        _apply(state, too_much)
    wrong_month = MeetingOutcome(fid, "board", state.turn - 1)
    with pytest.raises(MeetingRuleError):
        _apply(state, wrong_month)
    market = MeetingOutcome(fid, "call", state.turn, sentiment=MB.call.step * 2)
    with pytest.raises(MeetingRuleError):
        _apply(state, market)


def test_meeting_promises_do_not_crowd_out_press_promises() -> None:
    state = after_report()
    m = _play(_open(state, "board"), Move("commit"))
    state = _apply(state, outcome_action(m, _founder(state)))
    open_press = [p for p in promises.open_promises(state, CID) if p.kind in ("ship", "beat")]
    assert open_press == []
    assert promises.meeting_words(next(p for p in state.promises if p.kind == "commitment"))


def test_credibility_record_is_29_3s() -> None:
    """59.2's credibility is the company's 29.3 score (M48 decision 1)."""
    state = adjust_credibility(after_report(), CID, -20, "test", B)
    m = _open(state, "call")
    assert m.credibility == pytest.approx(credibility(state, CID, B), abs=0.1)
    company = state.player
    assert with_company(state, company) is not None
