"""M27b's tools (docs/formulas.md 40.7): staff for any group company, and (sub-task 11) the
chain targets (a)-(d). True values are read here; this is a tool, not the game. People added
are generated on stream `misc` (tests and tools only), as in m8.py."""

from __future__ import annotations

from dataclasses import replace

from tst.balance.game import PLAYER, Game
from tst.sim.hiring.models import PersonState
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.people.reveal import new_reveal_state
from tst.sim.rivals.setup import market_salary_cents
from tst.sim.rng import RngFactory
from tst.sim.state import with_employment, with_person, with_person_state, with_reveal


def add_staff_at(
    game: Game,
    company_id: int,
    role: str,
    level: str,
    count: int,
    skill: float | None = None,
    unit_id: int | None = None,
) -> list[int]:
    """`count` employees of `role` in `company_id` (any group company) at the market rate,
    seen by the player's company (script only)."""
    loaded = game.loaded
    data, balance = loaded.game_data, loaded.balance
    ids = []
    for _ in range(count):
        state = game.state
        pid, next_ids = state.next_ids.take("person")
        emp_id, next_ids = next_ids.take("employment")
        gen = RngFactory(state.save_meta.master_seed).stream(state.turn, "misc", pid)
        person = generate_person(
            gen, data, balance, state.turn, data.role(role), level, "north_america", person_id=pid
        )
        if skill is not None:
            person = replace(
                person, skills=person.skills.updated(dict.fromkeys(person.skills.keys(), skill))
            )
        state = replace(with_person(state, person), next_ids=next_ids)
        state = with_employment(
            state,
            Employment(
                id=emp_id,
                person_id=pid,
                company_id=company_id,
                role=role,
                level=level,
                salary_cents=market_salary_cents(role, level, balance, data),
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
                unit_id=unit_id,
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=balance.morale.new_hire))
        state = with_reveal(
            state,
            new_reveal_state(
                observer_company_id=PLAYER,
                person=person,
                turn=state.turn,
                rng=RngFactory(state.save_meta.master_seed),
                data=data,
                balance=balance,
            ),
        )
        game.state = state
        ids.append(pid)
    return ids
