"""Keep the org consistent when people leave (formulas.md 13.1, ADR-0015).

A leader who is no longer on staff stops leading their unit, and an active or filled plan
whose owner left pauses until it gets a new owner. Both write an inbox item. A filled or
closed plan gives up the job posts it opened (formulas.md 13.10).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import GameData
from tst.sim.hiring.models import Search
from tst.sim.log import LogItem, inbox_item
from tst.sim.org.models import HiringPlan
from tst.sim.state import GameState, with_exec_seat, with_plan, with_search, with_unit

OPEN_PLAN_STATUSES = ("active", "paused")  # plans that still use their role's searches


def _name(state: GameState, person_id: int) -> str:
    person = state.person(person_id)
    return f"{person.first_name} {person.last_name}"


def release_job_posts(state: GameState, plan: HiringPlan) -> tuple[GameState, list[Search]]:
    """The open job posts a filled or closed plan opened (formulas.md 13.10).

    A job post that another open plan for the same role uses passes to that plan (lowest
    plan id first) and stays open. Returns the state and the job posts to close.
    """
    to_close = []
    for search in state.open_searches(plan.company_id):
        if search.plan_id != plan.id or search.channel != "job_post":
            continue
        heir = next(
            (
                p
                for p in sorted(state.plans, key=lambda p: p.id)
                if p.id != plan.id
                and p.company_id == plan.company_id
                and p.role == search.role
                and p.status in OPEN_PLAN_STATUSES
            ),
            None,
        )
        if heir is None:
            to_close.append(search)
        else:
            state = with_search(state, replace(search, plan_id=heir.id))
    return state, to_close


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
    for seat in state.exec_seats:  # a departed executive's seat empties (M8, 18.3)
        if seat.person_id is not None and seat.person_id not in staff:
            logs.append(
                inbox_item(
                    state.turn,
                    seat.company_id,
                    "exec_left",
                    name=_name(state, seat.person_id),
                    seat=seat.seat.upper(),
                )
            )
            state = with_exec_seat(state, replace(seat, person_id=None, since_turn=state.turn))
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
