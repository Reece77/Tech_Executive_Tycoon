"""M8r finding 3 (Codex review 1, P2): a poached executive leaves their old company's seat.
Departure cleanup checks the seat's (unit's, plan's) own company, not "on anyone's staff":
phase 1 moves the poached person onto the rival's staff before cleanup runs."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.unit.test_hiring_phases import Game
from tests.unit.test_scaleup import FOUNDER, act, game, run, skilled
from tst.loader import LoadedData
from tst.sim.actions import AppointExecutive, CreateUnit, MovePerson, SetLeader
from tst.sim.errors import OrgRuleError
from tst.sim.org import executives as ex
from tst.sim.rivals.decisions import approach
from tst.sim.state import GameState, with_approach, with_person

CTO, NEXT = 2, 3


def test_a_poached_cto_leaves_the_seat_vacant(loaded: LoadedData) -> None:
    state = skilled(game(loaded, staff=2), CTO, 14.0)
    state = run(loaded, state, AppointExecutive(FOUNDER, "cto", CTO))
    state = run(loaded, state, CreateUnit(FOUNDER, "team", "Platform"))
    team = max(u.id for u in state.units)
    state = run(loaded, state, MovePerson(FOUNDER, CTO, team), SetLeader(FOUNDER, team, CTO))
    assert ex.effect_of(state, 1, "cto", loaded.balance) == pytest.approx(0.5)

    rival = next(c for c in state.companies if c.name == "Salesforce")
    state = approach(state, rival, CTO, loaded.balance, loaded.game_data)
    person = state.person(CTO)  # an unhappy, disloyal person takes a huge offer
    disloyal = person.personality.updated({"loyalty": 1.0})
    state = with_person(state, replace(person, personality=disloyal))
    state = with_approach(state, replace(state.approaches[0], offer_cents=40_000_000))
    g = Game(loaded, state, 400_000_000)
    notes: list[str] = []
    for _ in range(4):
        notes += [i.template or "" for i in g.turn().log_items]
        joined = g.state.employment_of(CTO)
        if joined is not None and joined.company_id == rival.id:
            break
    else:
        pytest.fail("the CTO never joined the rival")

    state = g.state
    assert state.seat_holder(1, "cto") is None
    assert ex.effect_of(state, 1, "cto", loaded.balance) == loaded.balance.exec_seats.vacant_effect
    assert "exec_left" in notes and "unit_leader_left" in notes
    assert next(u for u in state.units if u.id == team).leader_id is None
    state = act(
        loaded, skilled(state, NEXT, 12.0), AppointExecutive(FOUNDER, "cto", NEXT)
    ).new_state
    assert state.seat_holder(1, "cto") == NEXT


def test_a_holder_employed_elsewhere_counts_as_vacant(loaded: LoadedData) -> None:
    """effect_of, before cleanup has run: a holder whose employment is at another company."""
    state = skilled(game(loaded, staff=2), CTO, 14.0)
    state = run(loaded, state, AppointExecutive(FOUNDER, "cto", CTO))
    employment = state.employment_of(CTO)
    assert employment is not None
    from tst.sim.state import with_employment

    elsewhere = replace(employment, company_id=next(c.id for c in state.companies if c.id != 1))
    state = with_employment(state, elsewhere)
    assert ex.effect_of(state, 1, "cto", loaded.balance) == loaded.balance.exec_seats.vacant_effect


# --- Product manager, 2026-10-31: an appointment sets an exec salary (18.3) ----------------

MONTHS = 6


def _exec_rate(loaded: LoadedData, state: GameState, person_id: int) -> int:
    from tst.sim.hiring.formulas import market_mid_cents

    employment = state.employment_of(person_id)
    assert employment is not None
    region = loaded.game_data.region(state.person(person_id).region)
    band = loaded.game_data.role(employment.role).salary_band_mid_cents["exec"]
    return market_mid_cents(band, region.salary_multiplier_bp)


def test_an_appointment_pays_the_exec_market_rate(loaded: LoadedData) -> None:
    state = skilled(game(loaded, staff=2), CTO, 14.0)
    rate = _exec_rate(loaded, state, CTO)
    before = state.person_state(CTO).morale or 0
    out = act(loaded, state, AppointExecutive(FOUNDER, "cto", CTO))
    employment = out.new_state.employment_of(CTO)
    assert employment is not None and employment.salary_cents == rate
    assert employment.last_raise_turn == state.turn
    # +5 for the seat and +3 for the raise, each once (13.8).
    bonus = loaded.balance.exec_seats.appoint_morale + loaded.balance.org.raise_morale
    assert out.new_state.person_state(CTO).morale == pytest.approx(min(100, before + bonus))


def test_an_appointment_never_cuts_pay_and_takes_a_chosen_salary(loaded: LoadedData) -> None:
    state = skilled(game(loaded, staff=2), CTO, 14.0)
    rich = 40_000_000
    employment = state.employment_of(CTO)
    assert employment is not None
    from tst.sim.state import with_employment

    paid = with_employment(state, replace(employment, salary_cents=rich))
    out = act(loaded, paid, AppointExecutive(FOUNDER, "cto", CTO)).new_state
    assert out.employment_of(CTO).salary_cents == rich  # type: ignore[union-attr]
    chosen = act(loaded, state, AppointExecutive(FOUNDER, "cto", CTO, 25_000_000)).new_state
    assert chosen.employment_of(CTO).salary_cents == 25_000_000  # type: ignore[union-attr]
    with pytest.raises(OrgRuleError, match="below"):
        act(loaded, paid, AppointExecutive(FOUNDER, "cto", CTO, rich - 1))


def test_an_approach_after_appointment_reads_likely_to_stay(loaded: LoadedData) -> None:
    """At the default salary a rival's offer (the exec market rate) is no raise: the band
    reads "likely to stay" (it read "likely to go" while pay stayed at the old level)."""
    from tst.api.rival_views import band

    state = run(
        loaded, skilled(game(loaded, staff=2), CTO, 14.0), AppointExecutive(FOUNDER, "cto", CTO)
    )
    rival = next(c for c in state.companies if c.name == "Salesforce")
    state = approach(state, rival, CTO, loaded.balance, loaded.game_data)
    assert band(state, state.approaches[-1], loaded) == "likely to stay"
