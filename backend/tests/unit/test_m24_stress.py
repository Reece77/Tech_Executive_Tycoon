"""M24 stress and burnout (docs/formulas.md 32.1): the worked example; burnout's energy cut,
its critical event and its three answers; Holiday and critical events; and, as a property,
that a founder whose energy use stays at or below stress.comfort never burns out."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game
from tst.loader import load_all
from tst.sim.decisions import Decisions
from tst.sim.events.effects import apply_choice
from tst.sim.founder import stress
from tst.sim.founder.phase import BURNOUT_TEMPLATE, founder_step
from tst.sim.ledger import apply_entries
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, life_of, with_life, with_person_state
from tst.sim.turn import advance_turn

LOADED = load_all(DATA_DIR)
B, D = LOADED.balance, LOADED.game_data
SB = B.stress
CASH = {(1, "1000_cash"): 10_000_000_000}


def _months(used: float, n: int) -> list[float]:
    life = stress.new_life(1, B)
    out = []
    for turn in range(n):
        life, _ = stress.step(life, turn, used, False, 0, SB)
        out.append(life.stress)
    return out


def test_worked_example_all_energy() -> None:
    """32.1: using all 60 energy adds 40 x 0.4 = 16 a month: from 20, burnout in month 4."""
    assert _months(1.0, 4) == [36.0, 52.0, 68.0, 84.0]
    life = stress.new_life(1, B)
    began_at = None
    for turn in range(6):
        life, began = stress.step(life, turn, 1.0, False, 0, SB)
        if began:
            began_at = turn
    assert began_at == 3  # the fourth month
    assert life.burnouts == 1


def test_worked_example_three_quarters() -> None:
    """45 of 60 (0.75) adds 6 a month: burnout after 10 months."""
    assert stress.used_share(60, 15, 60) == 0.75
    life = stress.new_life(1, B)
    months = 0
    while not life.burnout:
        life, _ = stress.step(life, months, 0.75, False, 0, SB)
        months += 1
    assert months == 10
    assert life.stress == 80.0


def test_recovery_holiday_and_critical() -> None:
    life = replace(stress.new_life(1, B), stress=50.0)
    light, _ = stress.step(life, 0, 0.5, False, 0, SB)
    assert light.stress == 42.0  # -8
    away, _ = stress.step(life, 0, 0.0, True, 0, SB)
    assert away.stress == 17.0  # -8 - 25
    critical, _ = stress.step(life, 0, 0.5, False, 2, SB)
    assert critical.stress == 52.0  # -8 + 2 x 5
    floor, _ = stress.step(replace(life, stress=3.0), 0, 0.0, False, 0, SB)
    assert floor.stress == 0.0


def test_burnout_ends_below_forty() -> None:
    life = replace(stress.new_life(1, B), stress=49.0, burnout=True, burnout_turn=0)
    still, _ = stress.step(life, 1, 0.6, False, 0, SB)
    assert still.stress == 41.0 and still.burnout
    ended, _ = stress.step(still, 2, 0.6, False, 0, SB)
    assert ended.stress == 33.0 and not ended.burnout


def test_burnout_cuts_energy() -> None:
    assert stress.budget_after_cut(60, replace(stress.new_life(1, B), burnout=True), SB) == 42
    assert stress.budget_after_cut(60, stress.new_life(1, B), SB) == 60


def test_used_share_bounds() -> None:
    assert stress.used_share(None, 60, 60) == 0.0
    assert stress.used_share(0, 0, 60) == 0.0  # a month with no budget used nothing
    assert stress.used_share(40, 50, 60) == 0.0  # an event's bonus above the budget
    assert stress.used_share(42, 0, 60) == 1.0


@settings(max_examples=200, deadline=None)
@given(st.lists(st.floats(min_value=0.0, max_value=0.6), min_size=1, max_size=360))
def test_use_at_or_below_comfort_never_burns_out(uses: list[float]) -> None:
    """32.7 target 1: a founder whose energy use stays at or below 0.6 never burns out."""
    life = stress.new_life(1, B)
    for turn, used in enumerate(uses):
        life, began = stress.step(life, turn, used, False, 0, SB)
        assert not began and not life.burnout
        assert 0.0 <= life.stress <= SB.start


# --- Through the turn ------------------------------------------------------------------------


def _play(state: GameState, balances: dict[tuple[int, str], int], **kw: bool) -> GameState:
    result = advance_turn(state, Decisions(**kw), RngFactory(3), B, D, balances)
    balances.update(apply_entries(balances, result.ledger_entries))
    return result.new_state


def _spend_all(state: GameState) -> GameState:
    founder = state.founder_of(state.player.id)
    assert founder is not None
    return with_person_state(state, replace(state.person_state(founder.id), energy=0))


def test_four_full_months_burn_out_and_queue_the_event() -> None:
    state = fresh_game(LOADED)
    balances = dict(CASH)
    founder = state.founder_of(1)
    assert founder is not None
    for _ in range(4):
        state = _play(_spend_all(state), balances)
    life = life_of(state, founder.id)
    assert life is not None and life.burnout and life.stress == 84.0
    # The next month's budget is cut by 30%.
    assert state.person_state(founder.id).energy == life.budget
    assert life.budget is not None and life.budget < B.founder.energy_per_month
    (event,) = [e for e in state.events if e.template_id == BURNOUT_TEMPLATE]
    assert event.severity == "critical" and event.turn == state.turn


def test_holiday_month_lowers_stress() -> None:
    state = fresh_game(LOADED)
    founder = state.founder_of(1)
    assert founder is not None
    state = with_life(state, replace(stress.new_life(founder.id, B), stress=60.0))
    state = _play(state, dict(CASH), holiday=True)
    life = life_of(state, founder.id)
    assert life is not None and life.stress == 60.0 - 8 - 25


def _burnt(state: GameState) -> tuple[GameState, int]:
    founder = state.founder_of(1)
    assert founder is not None
    life = replace(stress.new_life(founder.id, B), stress=82.0, burnout=True, burnout_turn=0)
    return with_life(state, life), founder.id


def test_answers_rest_push_on_and_delegate() -> None:
    from tst.sim.events.models import Effect, EventChoice, GameEvent

    state, fid = _burnt(fresh_game(LOADED))
    event = GameEvent(
        id=999,
        company_id=1,
        turn=state.turn,
        template_id=BURNOUT_TEMPLATE,
        category="founder",
        severity="critical",
        trigger="follow_up",
        strength=1.0,
        status="open",
        choices=tuple(
            EventChoice(k, k, (Effect("founder_step", f"founder:{fid}", 0.0, stat),))
            for k, stat in (("A", "rest"), ("B", "delegate"), ("C", "push_on"))
        ),
    )
    state = replace(state, events=(*state.events, event))
    rested, _, _ = apply_choice(state, event, "A", B, D, auto=False)
    life = life_of(rested, fid)
    assert life is not None and life.rest_turn == state.turn
    assert rested.person_state(fid).energy == 0  # this month off
    delegated, _ = founder_step(state, event, "delegate", B, D)
    assert life_of(delegated, fid) == life_of(state, fid)
    pushed, _ = founder_step(state, event, "push_on", B, D)
    after = life_of(pushed, fid)
    assert after is not None
    assert after.stress == 87.0
    assert after.reckless == B.persona.start + B.persona.sources["pushed_on"]
    # A month off counts as a month away: stress falls by recover + holiday.
    end = _play(rested, dict(CASH))
    final = life_of(end, fid)
    assert final is not None and final.stress == 82.0 - 8 - 25 + 5  # + the critical answered
