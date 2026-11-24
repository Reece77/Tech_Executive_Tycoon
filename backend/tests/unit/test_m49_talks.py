"""M49 sub-tasks 1-3 (docs/formulas.md 61.1-61.2): talks open on the engine's facts with
seeded hidden draws, moves are checked against the question, effects stay within their
bounds, interviews answer their press event through 29.1's tone, crisis conferences move the
brand, credibility and persona, and one-to-ones move morale and loyalty, can keep a person
from a rival, give a raise and record a promised promotion that is kept or broken."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game, make_person, with_employee, with_product
from tst.loader import LoadedData, load_all
from tst.sim.actions import apply_action
from tst.sim.errors import TalkRuleError
from tst.sim.events.models import Effect, EventChoice, GameEvent
from tst.sim.ledger import CASH
from tst.sim.medical.models import Recall
from tst.sim.press import moments, promises
from tst.sim.press.models import PressMoment
from tst.sim.rivals.models import PoachApproach
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_event, with_press_moment
from tst.sim.talks import engine, opening
from tst.sim.talks.actions import TalkOutcome, outcome_action
from tst.sim.talks.config import MOVES, ONE_TO_ONE_MOVES
from tst.sim.talks.models import Move, Talk

RICH = {(1, CASH): 10**14}
LOADED = load_all(Path(__file__).resolve().parents[2] / "data")
SALARY = 10_000_000


def _apply(state: GameState, action: object, loaded: LoadedData) -> GameState:
    out = apply_action(
        state,
        action,  # type: ignore[arg-type]
        RngFactory(state.save_meta.master_seed),
        loaded.balance,
        loaded.game_data,
        RICH,
        seq=1,
    )
    return out.new_state


def _founder(state: GameState) -> int:
    f = state.founder_of(state.player.id)
    assert f is not None
    return f.id


def _staffed(loaded: LoadedData, level: str = "mid") -> tuple[GameState, int]:
    state = replace(fresh_game(loaded), turn=24)
    pid, ids = state.next_ids.take("person")
    state = replace(state, next_ids=ids)
    state = with_employee(loaded, state, make_person(loaded, pid, level=level), SALARY)
    return state, pid


def _approached(loaded: LoadedData) -> tuple[GameState, int, PoachApproach]:
    state, pid = _staffed(loaded)
    rival = next(c for c in state.rivals() if c.alive)
    approach = PoachApproach(1, rival.id, pid, 13_000_000, state.turn - 1)
    return replace(state, approaches=(approach,)), pid, approach


def _one(state: GameState, pid: int, loaded: LoadedData, **kw: object) -> Talk:
    return opening.open_one_to_one(
        state,
        pid,
        RngFactory(state.save_meta.master_seed),
        loaded.balance,
        loaded.game_data,
        morale_shown=65,
        **kw,  # type: ignore[arg-type]
    )


def _play(talk: Talk, loaded: LoadedData, *moves: str) -> Talk:
    while talk.status == "open":
        talk = engine.play(talk, tuple(Move(m) for m in moves), loaded.balance.talks)
    return talk


# --- One-to-ones (61.2) ---------------------------------------------------------------------


def test_a_one_to_one_raises_the_rivals_approach_and_offers_a_promotion(
    loaded: LoadedData,
) -> None:
    state, pid, approach = _approached(loaded)
    talk = _one(state, pid, loaded)
    topics = [q.topic for q in talk.questions]
    assert topics[:3] == ["morale", "ambition", "approach"]
    assert talk.subject.approach_id == approach.id
    assert talk.offer is not None and talk.offer.kind == "promotion"
    assert "senior" in talk.offer.words
    # the rival's offer amount is never in the talk's words
    words = " ".join(q.question + " ".join(q.facts) for q in talk.questions)
    assert "130,000" not in words and "13,000,000" not in words
    # same seed, same month: the same hidden draws
    assert _one(state, pid, loaded).hidden == talk.hidden


def test_moves_the_question_does_not_bear_out_are_neutral(loaded: LoadedData) -> None:
    state, pid = _staffed(loaded, level="principal")  # the top of the ladder: no promotion
    talk = _one(state, pid, loaded)
    assert talk.offer is None
    q = talk.questions[1]
    checked = engine.check_moves(
        talk, q, (Move("promise_promotion"), Move("bribe"), Move("listen"), Move("listen")), 3
    )
    assert [m.kind for m in checked] == ["neutral", "listen"]


@settings(max_examples=60, deadline=None)
@given(st.lists(st.lists(st.sampled_from(ONE_TO_ONE_MOVES), min_size=1, max_size=3), min_size=4))
def test_a_one_to_ones_effects_stay_within_their_bounds(moves: list[list[str]]) -> None:
    loaded = LOADED
    state, pid, _a = _approached(loaded)
    talk = _one(state, pid, loaded)
    tb = loaded.balance.talks
    for ms in moves:
        if talk.status != "open":
            break
        talk = engine.play(talk, tuple(Move(m) for m in ms), tb)
    if talk.effects is None:
        return
    e = talk.effects
    assert abs(e.morale) <= tb.one_to_one.morale_step
    assert abs(e.loyalty) <= tb.one_to_one.loyalty_step
    assert 0 <= e.retain_chance <= tb.one_to_one.retain_cap


def test_a_good_one_to_one_lifts_morale_and_can_keep_an_approached_person(
    loaded: LoadedData,
) -> None:
    state, pid, approach = _approached(loaded)
    talk = _play(_one(state, pid, loaded), loaded, "listen", "praise", "offer_raise")
    e = talk.effects
    assert e is not None and e.morale > 0 and e.retain_chance > 0 and e.offer_raise
    action = outcome_action(
        talk, _founder(state), SALARY, loaded.balance.talks.one_to_one.raise_share
    )
    after = _apply(state, action, loaded)
    morale_before = state.person_state(pid).morale or 0
    assert (after.person_state(pid).morale or 0) > morale_before
    e2 = after.employment_of(pid)
    assert e2 is not None and e2.salary_cents == round(SALARY * 1.05)
    energy = state.person_state(_founder(state)).energy
    if energy is not None:  # the talk's 2 and the raise's own cost
        assert (after.person_state(_founder(state)).energy or 0) < energy - 1
    status = next(a for a in after.approaches if a.id == approach.id).status
    assert status in ("pending", "declined")  # the drawn retention chance
    # the same outcome on the same seed gives the same answer
    again = _apply(state, action, loaded)
    assert next(a for a in again.approaches if a.id == approach.id).status == status


def test_a_kept_promotion_promise_lifts_morale_and_a_broken_one_costs_double(
    loaded: LoadedData,
) -> None:
    state, pid = _staffed(loaded)
    talk = _play(_one(state, pid, loaded), loaded, "promise_promotion")
    action = outcome_action(talk, _founder(state), SALARY, 0.05)
    after = _apply(state, action, loaded)
    p = next(x for x in after.promises if x.kind == "promotion")
    assert p.level == pid and p.deadline_turn == state.turn + 12
    rng = RngFactory(state.save_meta.master_seed)
    b, d = loaded.balance, loaded.game_data
    # never promoted: broken at the deadline, morale -8 (2 x 4) and the chance of leaving x2
    due = replace(after, turn=p.deadline_turn)
    morale = due.person_state(pid).morale or 0
    broken, logs = promises.check(due, rng, b, d)
    assert next(x for x in broken.promises if x.id == p.id).status == "broken"
    assert (broken.person_state(pid).morale or 0) == pytest.approx(morale - 8)
    assert promises.leave_mult(broken, b) == {pid: 2.0}
    assert any(log.template == "promotion_broken" for log in logs)
    # promoted in time: kept
    from tst.sim.actions.org import Promote

    promoted = _apply(after, Promote(_founder(state), pid), loaded)
    kept, _ = promises.check(promoted, rng, b, d)
    assert next(x for x in kept.promises if x.id == p.id).status == "kept"
    assert promises.leave_mult(kept, b) == {}


def test_a_promotion_promise_never_counts_as_a_public_promise(loaded: LoadedData) -> None:
    state, pid = _staffed(loaded)
    talk = _play(_one(state, pid, loaded), loaded, "promise_promotion")
    after = _apply(state, outcome_action(talk, _founder(state), SALARY, 0.05), loaded)
    assert promises.promise_words(after, after.promises[-1], loaded.game_data).startswith(
        "promote "
    )


def test_the_outcome_rechecks_its_bounds(loaded: LoadedData) -> None:
    state, pid = _staffed(loaded)
    bad = TalkOutcome(
        actor_id=_founder(state),
        talk_kind="one_to_one",
        period_turn=state.turn,
        source="person",
        subject_key=pid,
        person_id=pid,
        morale=50.0,
    )
    with pytest.raises(TalkRuleError):
        _apply(state, bad, loaded)
    with pytest.raises(TalkRuleError):
        _apply(state, replace(bad, morale=1.0, period_turn=state.turn - 1), loaded)


def test_a_delegated_one_to_one_uses_the_holders_factor(loaded: LoadedData) -> None:
    state, pid = _staffed(loaded)
    holder, _ids = state.next_ids.take("person")
    founder_talk = _one(state, pid, loaded)
    delegated = _one(state, pid, loaded, delegate_id=_founder(state))
    tb = loaded.balance.talks
    assert tb.skill.band.lo <= delegated.hidden.skill <= tb.skill.band.hi
    assert delegated.delegate_id == _founder(state)
    played = engine.replay(delegated, engine.delegated_moves(delegated), tb)
    assert played.status == "done" and founder_talk.delegate_id is None
    del holder


# --- Crisis conferences (61.1) -------------------------------------------------------------


def _recalled(loaded: LoadedData) -> GameState:
    state = with_product(replace(fresh_game(loaded), turn=30))
    product = next(p for p in state.company_products(state.player.id))
    recall = Recall(1, state.player.id, product.id, state.turn - 1, "I", 100, 10_000, False, 33)
    return replace(state, med_recalls=(recall,))


def test_a_class_i_recall_brings_a_crisis_conference(loaded: LoadedData) -> None:
    state = _recalled(loaded)
    subjects = opening.crisis_subjects(state, loaded.balance.talks)
    assert [s.source for s in subjects] == ["recall"]
    later = replace(state, turn=state.turn + 2)
    assert opening.crisis_subjects(later, loaded.balance.talks) == []


def test_candour_beats_deflection_in_a_crisis(loaded: LoadedData) -> None:
    state = _recalled(loaded)
    subject = opening.crisis_subjects(state, loaded.balance.talks)[0]
    rng = RngFactory(state.save_meta.master_seed)
    talk = opening.open_press(state, "crisis", subject, rng, loaded.balance, loaded.game_data)
    assert all(m in MOVES["crisis"] for m in ("apologise", "take_responsibility"))
    candid = _play(talk, loaded, "apologise", "take_responsibility")
    deflect = _play(talk, loaded, "deflect")
    assert candid.effects is not None and deflect.effects is not None
    assert candid.effects.brand_pct > 0 > deflect.effects.brand_pct
    assert candid.effects.persona is not None and candid.effects.persona[0] == "beloved"
    assert deflect.effects.persona is not None and deflect.effects.persona[0] == "ruthless"
    assert deflect.effects.inspection_chance > 0 == candid.effects.inspection_chance
    cid = state.player.id
    after = _apply(state, outcome_action(candid, _founder(state), 0, 0.05), loaded)
    assert moments.credibility(after, cid, loaded.balance) > moments.credibility(
        state, cid, loaded.balance
    )
    assert any(m.stat == "brand_target" and m.value_pct > 0 for m in after.modifiers)


# --- Interviews (61.1) ---------------------------------------------------------------------


def _press_month(loaded: LoadedData) -> GameState:
    state = with_product(replace(fresh_game(loaded), turn=30))
    cid = state.player.id
    product = next(p for p in state.company_products(cid))
    moment = PressMoment(
        id=1,
        company_id=cid,
        trigger="launch",
        turn=state.turn - 1,
        status="queued",
        event_turn=state.turn,
        product_id=product.id,
    )
    choices = tuple(
        EventChoice(k, k, (Effect("press_step", f"company:{cid}", stat=t),))
        for k, t in (("A", "measured"), ("B", "bold"), ("C", "deflect"))
    )
    event = GameEvent(
        id=1,
        company_id=cid,
        turn=state.turn,
        template_id="press_launch",
        category="press",
        severity="major",
        trigger="press",
        strength=1.0,
        product_id=product.id,
        status="open",
        choices=choices,
    )
    return with_event(with_press_moment(state, moment), event)


def test_an_interview_answers_its_press_event_with_the_tone_it_adds_up_to(
    loaded: LoadedData,
) -> None:
    state = _press_month(loaded)
    found = opening.press_subject(state, loaded.game_data)
    assert found is not None
    kind, subject = found
    assert kind == "interview" and subject.event_id == 1
    rng = RngFactory(state.save_meta.master_seed)
    talk = opening.open_press(state, kind, subject, rng, loaded.balance, loaded.game_data)
    assert 2 <= len(talk.questions) <= 4
    bold = _play(talk, loaded, "bold_claim")
    assert bold.effects is not None and bold.effects.tone == "bold"
    after = _apply(state, outcome_action(bold, _founder(state), 0, 0.05), loaded)
    event = after.event(1)
    assert event is not None and event.chosen == "B"
    moment = next(m for m in after.press_moments if m.id == 1)
    assert moment.tone == "bold"
    # a deflection makes no promise even when asked to
    sly = _play(talk, loaded, "no_comment", "promise")
    assert sly.effects is not None and sly.effects.tone == "deflect"
    assert sly.effects.promise is None


def test_skipping_a_talk_moves_nothing(loaded: LoadedData) -> None:
    state, pid, _a = _approached(loaded)
    talk = engine.skip(_one(state, pid, loaded))
    assert talk.status == "skipped" and talk.effects is None
    with pytest.raises(TalkRuleError):
        outcome_action(talk, _founder(state), SALARY, 0.05)
