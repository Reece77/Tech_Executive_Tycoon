"""M10b critical events (docs/formulas.md 23.3): a key exit, a security breach, an outage and a
press crisis each bring a critical event when their condition holds; spacing (one critical in
any six months) still holds; a counter-offer keeps someone who resigned."""

from __future__ import annotations

from dataclasses import replace

from tests.helpers import fresh_game, make_person, with_employee, with_product
from tst.loader import LoadedData
from tst.sim.data_models import Balance
from tst.sim.events.director import direct
from tst.sim.events.effects import apply_choice
from tst.sim.events.models import Effect, EventChoice, GameEvent, Storyline
from tst.sim.events.triggers import key_people
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_employment, with_event, with_storyline

CASH = 10**10


def _balance(loaded: LoadedData, **crisis: float) -> Balance:
    ev = loaded.balance.events
    events = ev.model_copy(update={"crisis": ev.crisis.model_copy(update=crisis)})
    return loaded.balance.model_copy(update={"events": events})


def _queued(
    state: GameState, balance: Balance, loaded: LoadedData, seed: int = 1
) -> list[GameEvent]:
    out, _ = direct(state, state, RngFactory(seed), balance, loaded.game_data, CASH, 0, ())
    return [e for e in out.events if e.status == "pending"]


def _staffed(loaded: LoadedData, n: int = 10) -> GameState:
    state = fresh_game(loaded)
    for pid in range(2, 2 + n):
        state = with_employee(loaded, state, make_person(loaded, pid), 9_000_000)
    return state


def _resign(state: GameState, person_id: int) -> GameState:
    e = state.employment_of(person_id)
    assert e is not None
    return with_employment(
        state, replace(e, status="notice", end_turn=state.turn + 1, end_reason="resigned")
    )


def test_a_key_exit_brings_a_critical_event_and_a_counter_offer_keeps_them(
    loaded: LoadedData,
) -> None:
    state = _staffed(loaded)
    star = min(key_people(state, loaded.game_data, loaded.balance))
    state = _resign(state, star)
    (event,) = [e for e in _queued(state, loaded.balance, loaded) if e.severity == "critical"]
    assert (event.template_id, event.trigger, event.person_ids) == (
        "key_exit_crisis",
        "key_exit",
        (star,),
    )
    written = replace(
        event,
        status="open",
        choices=(EventChoice("A", "Counter", (Effect("retain", f"person:{star}"),)),),
    )
    state = with_event(state, written)
    after, _, logs = apply_choice(state, written, "A", loaded.balance, loaded.game_data, auto=False)
    employment = after.employment_of(star)
    assert employment is not None and employment.status == "active"
    assert employment.end_turn is None and any(i.template == "retained" for i in logs)


def test_an_ordinary_resignation_is_no_crisis(loaded: LoadedData) -> None:
    state = _staffed(loaded)
    ordinary = max(
        e.person_id
        for e in state.staff(1)
        if e.person_id not in key_people(state, loaded.game_data, loaded.balance)
        and e.person_id != 1
    )
    state = _resign(state, ordinary)
    assert not [e for e in _queued(state, loaded.balance, loaded) if e.severity == "critical"]


def _live(loaded: LoadedData, customers: float, quality: float) -> GameState:
    state = _staffed(loaded, 2)
    return with_product(state, customers={"smb": customers}, quality=quality)


def test_a_breach_needs_customers_and_falls_with_security(loaded: LoadedData) -> None:
    sure = _balance(loaded, breach_chance=1.0, outage_chance=0.0)
    state = _live(loaded, 2_000.0, 60.0)
    (event,) = [e for e in _queued(state, sure, loaded) if e.severity == "critical"]
    assert (event.template_id, event.trigger) == ("security_breach_crisis", "security_breach")
    assert not [
        e for e in _queued(_live(loaded, 500.0, 60.0), sure, loaded) if e.severity == "critical"
    ]
    # Full coverage: every team member at security 15 or more makes a breach impossible.
    secure = state
    for p in state.people:
        if state.employment_of(p.id) is not None:
            skills = p.skills.updated({"security": 18.0})
            secure = replace(
                secure,
                people=tuple(
                    q if q.id != p.id else replace(p, skills=skills) for q in secure.people
                ),
            )
    assert not [e for e in _queued(secure, sure, loaded) if e.severity == "critical"]


def test_an_outage_needs_a_busy_low_quality_product(loaded: LoadedData) -> None:
    sure = _balance(loaded, breach_chance=0.0, outage_chance=1.0)
    (event,) = [
        e for e in _queued(_live(loaded, 6_000.0, 40.0), sure, loaded) if e.severity == "critical"
    ]
    assert (event.template_id, event.trigger) == ("outage_crisis", "outage")
    for customers, quality in ((6_000.0, 50.0), (3_000.0, 40.0)):
        queued = _queued(_live(loaded, customers, quality), sure, loaded)
        assert not [e for e in queued if e.severity == "critical"]


def _press(loaded: LoadedData) -> GameState:
    state = _live(loaded, 100.0, 60.0)
    pid = state.company_products(1)[0].id
    story = Storyline(
        id=1,
        company_id=1,
        key="press_scrutiny",
        title="Press scrutiny",
        step=1,
        started_turn=0,
        summary="A reporter is digging.",
        product_id=pid,
        next_turn=state.turn + 1,
        next_template="press_scrutiny_2",
    )
    return with_storyline(replace(state, next_ids=replace(state.next_ids, storyline=2)), story)


def test_a_press_story_becomes_a_pr_crisis(loaded: LoadedData) -> None:
    (event,) = [e for e in _queued(_press(loaded), loaded.balance, loaded) if e.storyline_id == 1]
    assert (event.template_id, event.severity, event.trigger) == (
        "press_scrutiny_2",
        "critical",
        "pr_crisis",
    )


def test_spacing_holds_one_critical_in_six_months(loaded: LoadedData) -> None:
    state = _press(loaded)
    earlier = GameEvent(
        id=900,
        company_id=1,
        turn=state.turn - 2 if state.turn >= 2 else state.turn,
        template_id="runway_payroll_crunch",
        category="finance",
        severity="critical",
        trigger="runway_short",
        strength=1.0,
        status="answered",
    )
    state = with_event(state, earlier)
    (event,) = [e for e in _queued(state, loaded.balance, loaded) if e.storyline_id == 1]
    assert (event.severity, event.trigger) == ("major", "storyline")
    sure = _balance(loaded, breach_chance=1.0, outage_chance=1.0)
    busy = with_event(_live(loaded, 6_000.0, 40.0), earlier)
    assert not [e for e in _queued(busy, sure, loaded) if e.severity == "critical" and e.id != 900]
