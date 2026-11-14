"""Automate everything (docs/formulas.md 40.8): every area the player manages goes to the
eligible person with the best displayed fit, seat holders first, then the CEO, then leads,
never more areas than a person's energy covers at the areas' costs, with default limits. The
plan is shown for confirmation before anything changes."""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.automation import owners
from tst.sim.automation.run import month_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.money import Cents
from tst.sim.state import GameState

KIND_ORDER = {"seat": 0, "ceo": 1, "subsidiary_ceo": 1, "lead": 2}


@dataclass(frozen=True, slots=True)
class Assignment:
    area: str
    person_id: int
    limit_cents: int


def energy_left(state: GameState, person_id: int, b: Balance, data: GameData) -> int:
    """A person's monthly automation energy after the areas they already own (40.3)."""
    used = sum(
        owners.area_def(b, o.area).energy
        for o in state.owners_of(state.player.id)
        if o.person_id == person_id
    )
    return month_energy(state, person_id, b, data) - used


def automate_everything(
    state: GameState, cash: Cents, b: Balance, data: GameData
) -> list[Assignment]:
    company = state.player.id
    left: dict[int, int] = {}
    out: list[Assignment] = []
    limit = owners.default_limit(cash, b)
    for area in owners.area_keys(b):
        if state.area_owner(company, area) is not None:
            continue
        cost = owners.area_def(b, area).energy
        people = owners.eligible_people(state, company, area, b)
        ranked = sorted(
            people,
            key=lambda t: (
                KIND_ORDER[t[1]],
                -owners.shown_area_score(state, company, area, t[0], b),
                t[0],
            ),
        )
        for person_id, _ in ranked:
            room = left.get(person_id)
            if room is None:
                room = energy_left(state, person_id, b, data)
            if room < cost:
                left[person_id] = room
                continue
            left[person_id] = room - cost
            out.append(Assignment(area, person_id, limit))
            break
    return out
