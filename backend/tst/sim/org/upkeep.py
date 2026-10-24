"""Keep the org consistent when people leave (formulas.md 13.1, ADR-0015).

A leader who is no longer on staff stops leading their unit, and an active or filled plan
whose owner left pauses until it gets a new owner. Both write an inbox item.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import GameData
from tst.sim.log import LogItem, inbox_item
from tst.sim.state import GameState, with_plan, with_unit


def _name(state: GameState, person_id: int) -> str:
    person = state.person(person_id)
    return f"{person.first_name} {person.last_name}"


def detach_departed(state: GameState, data: GameData) -> tuple[GameState, tuple[LogItem, ...]]:
    staff = {e.person_id for e in state.employments if e.counts_as_staff}
    logs: list[LogItem] = []
    for unit in state.units:
        if unit.status == "active" and unit.leader_id is not None and unit.leader_id not in staff:
            logs.append(
                inbox_item(
                    state.turn,
                    unit.company_id,
                    "unit_leader_left",
                    name=_name(state, unit.leader_id),
                    unit=unit.name,
                )
            )
            state = with_unit(state, replace(unit, leader_id=None))
    for plan in state.plans:
        if plan.status in ("active", "filled") and plan.owner_id not in staff:
            state = with_plan(state, replace(plan, status="paused"))
            logs.append(
                inbox_item(
                    state.turn,
                    plan.company_id,
                    "plan_paused",
                    name=_name(state, plan.owner_id),
                    role=data.role(plan.role).label.lower(),
                )
            )
    return state, tuple(logs)
