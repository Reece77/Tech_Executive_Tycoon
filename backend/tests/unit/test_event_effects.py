"""Choices and critical events (docs/formulas.md 16.3; ADR-0006 amended; M6 sub-task 6):
each effect applies at once when the player chooses (energy 0); unanswered minor and major
events take their first choice at Continue; an open critical event blocks Continue until
answered, and its follow-up arrives the next month."""

from __future__ import annotations

import pytest

from tests.helpers import fresh_game, make_person, with_employee, with_product
from tests.unit.test_hiring_phases import Game
from tst.loader import LoadedData
from tst.sim.actions import ChooseEvent
from tst.sim.errors import CriticalEventOpenError, EventError
from tst.sim.events.models import Effect, EventChoice, GameEvent
from tst.sim.ledger import CASH, OTHER_INCOME
from tst.sim.people.relationships import pair_key
from tst.sim.state import GameState, with_event

A, B = 2, 3


def _game(loaded: LoadedData) -> Game:
    state = fresh_game(loaded)
    for pid in (A, B):
        state = with_employee(loaded, state, make_person(loaded, pid), 9_000_000)
    state = with_product(state, customers={"smb": 100.0}, quality=40.0, brand=10.0)
    game = Game(loaded, state, 400_000_000)
    game.turn()  # relationships start in phase 8
    return game


def _open(state: GameState, choices: tuple[EventChoice, ...], **kw: object) -> GameEvent:
    fields = {
        "id": 500,
        "company_id": 1,
        "turn": state.turn,
        "template_id": "low_morale_checkin",
        "category": "personnel",
        "severity": "major",
        "trigger": "low_morale",
        "strength": 0.6,
        "person_ids": (A,),
        "product_id": state.company_products(1)[0].id,
        "segment": "smb",
        "cash_base_cents": 50_000_000,
        "status": "open",
        "title": "Test",
        "body": "Body",
        "choices": choices,
    }
    fields.update(kw)
    return GameEvent(**fields)  # type: ignore[arg-type]


def test_each_effect_applies_when_chosen(loaded: LoadedData) -> None:
    game = _game(loaded)
    s = game.state
    product = s.company_products(1)[0].id
    rel_before = s.relationship_map()[pair_key(A, B)].value
    cash_before = game.balances[(1, CASH)]
    customers_before = s.segments_of(product)[0].customers
    effects = (
        Effect("morale_delta", f"person:{A}", 10),
        Effect("cash_delta", "company:1", -1_500_000),
        Effect("quality_delta", f"product:{product}", 3),
    )
    more = (
        Effect("brand_delta", f"product:{product}", 5),
        Effect("customers_pct", f"product:{product}", -3),
        Effect("relationship_delta", f"pair:{A}-{B}", -20),
    )
    last = (
        Effect("salary_change", f"person:{B}", 10),
        Effect("board_confidence", "board", 6),
        Effect("energy_delta", "founder:1", -10),
    )
    for i, chosen in enumerate((effects, more, last)):
        event = _open(
            game.state, (EventChoice("A", "a", ()), EventChoice("B", "b", chosen)), id=500 + i
        )
        game.state = with_event(game.state, event)
        game.act(ChooseEvent(1, event.id, "B"))
    after = game.state
    assert after.person_state(A).morale == pytest.approx(min(100, s.person_state(A).morale + 10))  # type: ignore[operator]
    assert game.balances[(1, CASH)] == cash_before - 1_500_000
    p0, p1 = s.product(product), after.product(product)
    assert p1.quality == p0.quality + 3 and p1.brand == p0.brand + 5  # type: ignore[union-attr]
    assert after.segments_of(product)[0].customers == pytest.approx(customers_before * 0.97)
    assert after.relationship_map()[pair_key(A, B)].value == pytest.approx(rel_before - 20)
    assert after.employment_of(B).salary_cents == 9_900_000  # type: ignore[union-attr]
    assert [e.status for e in after.events if e.id >= 500] == ["answered"] * 3
    founder_energy = after.person_state(1).energy
    game.turn()
    assert game.state.person_state(1).energy == loaded.balance.founder.energy_per_month - 10
    assert founder_energy is not None


def test_a_gain_posts_to_other_income_and_resign_gives_notice(loaded: LoadedData) -> None:
    game = _game(loaded)
    event = _open(
        game.state,
        (
            EventChoice(
                "A",
                "a",
                (Effect("cash_delta", "company:1", 300_000), Effect("resign", f"person:{A}")),
            ),
            EventChoice("B", "b", ()),
        ),
    )
    game.state = with_event(game.state, event)
    game.act(ChooseEvent(1, event.id, "A"))
    assert game.balances[(1, OTHER_INCOME)] == -300_000
    assert game.state.employment_of(A).status == "notice"  # type: ignore[union-attr]
    with pytest.raises(EventError):
        game.act(ChooseEvent(1, event.id, "B"))  # answered already


def test_continue_answers_minor_and_major_with_the_first_choice(loaded: LoadedData) -> None:
    game = _game(loaded)
    before = game.state.person_state(A).morale
    event = _open(
        game.state,
        (
            EventChoice("A", "first", (Effect("morale_delta", f"person:{A}", -5),)),
            EventChoice("B", "b", ()),
        ),
        severity="minor",
    )
    game.state = with_event(game.state, event)
    game.turn()
    closed = game.state.event(event.id)
    assert closed is not None and closed.status == "auto" and closed.chosen == "A"
    assert closed.resolved_turn == event.turn
    assert before is not None


def test_a_critical_event_blocks_continue_and_brings_its_follow_up(loaded: LoadedData) -> None:
    game = _game(loaded)
    event = _open(
        game.state,
        (
            EventChoice("A", "a", (Effect("follow_up", ""),)),
            EventChoice("B", "b", (Effect("follow_up", ""),)),
        ),
        severity="critical",
        template_id="runway_payroll_crunch",
        category="finance",
        trigger="runway_short",
    )
    game.state = with_event(game.state, event)
    with pytest.raises(CriticalEventOpenError) as blocked:
        game.turn()
    assert blocked.value.event_id == event.id
    game.act(ChooseEvent(1, event.id, "B"))
    assert [q.template_id for q in game.state.queued] == ["runway_aftermath"]
    result = game.turn()  # Continue works; the follow-up is queued for next month
    follow = [r for r in result.event_requests if r.template_id == "runway_aftermath"]
    assert len(follow) == 1 and follow[0].turn == game.state.turn
    assert game.state.queued[0].done
