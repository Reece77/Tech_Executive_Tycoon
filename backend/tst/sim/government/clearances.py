"""Staff and facility clearances (docs/formulas.md 57.3).

**A staff clearance** is requested for an employee at a level (the action, its investigation's
price to 6990). At the request (stream `defence` (2, person_id)): the months to a decision are
`sponsor_months` + `median_of_p90` x the level's fastest-90% days that year / 30.44, x a
mean-one lognormal (`sigma`), at least 1; the case never clears with the level's `never_share` x
(1 + `integrity_mult` x (10 - integrity) / 10), clipped to [0, 1]. Both stay hidden until the
decision month (57.7): the screen shows "pending". A cleared person who leaves the company lapses
(the employer holds the clearance).

**A facility clearance** is sponsored for one of the company's facilities (`facility_cost_cents`),
decided after U(`facility_clearance_months`) months (stream (2, 0, facility_id)); it always
clears. Classified work needs both (sourcing.requirements)."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.government import draws
from tst.sim.government.config import Level
from tst.sim.government.data import file, year_of
from tst.sim.government.models import Clearance, FacilityClearance
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

DAYS_A_MONTH: Final = 30.44  # tunable-exempt: calendar
INTEGRITY_MID: Final = 10.0  # tunable-exempt: personality is 1-20
FACILITY_KEY: Final = 0  # tunable-exempt: (2, 0, facility_id) keeps facilities apart from people


def draw_clearance(
    state: GameState,
    person_id: int,
    company_id: int,
    level: Level,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> Clearance:
    cb = balance.government.clearances
    spec = file(data).clearances[level]
    g = draws.gen(rng, state.turn, draws.CLEARANCE, person_id)
    median = cb.sponsor_months + cb.median_of_p90 * spec.p90_at(year_of(state.turn)) / DAYS_A_MONTH
    months = median * dmath.exp(cb.sigma * float(g.normal()))
    person = state.person(person_id)
    integrity = person.personality.as_dict().get("integrity", INTEGRITY_MID)
    never = spec.never_share * (1 + cb.integrity_mult * (INTEGRITY_MID - integrity) / INTEGRITY_MID)
    denied = float(g.random()) < max(0.0, min(1.0, never))
    return Clearance(
        person_id=person_id,
        company_id=company_id,
        level=level,
        requested_turn=state.turn,
        due_turn=state.turn + max(1, round(months)),
        outcome="denied" if denied else "cleared",
    )


def draw_facility(
    state: GameState, facility_id: int, company_id: int, rng: RngFactory, data: GameData
) -> FacilityClearance:
    r = file(data).facility_clearance_months
    g = draws.gen(rng, state.turn, draws.CLEARANCE, FACILITY_KEY, facility_id)
    months = int(g.integers(round(r.lo), round(r.hi) + 1))
    return FacilityClearance(
        facility_id=facility_id,
        company_id=company_id,
        requested_turn=state.turn,
        due_turn=state.turn + months,
    )


def month(state: GameState) -> tuple[GameState, list[LogItem]]:
    """Decisions due this month; cleared people who left lapse."""
    if not state.clearances and not state.facility_clearances:
        return state, []
    turn = state.turn
    logs: list[LogItem] = []
    out = []
    for c in state.clearances:
        if c.status == "pending" and turn >= c.due_turn:
            c = replace(c, status=c.outcome, decided_turn=turn)
            person = state.person(c.person_id)
            logs.append(
                inbox_item(
                    turn,
                    c.company_id,
                    "clearance_decided",
                    link_kind="person",
                    link_id=c.person_id,
                    name=f"{person.first_name} {person.last_name}",
                    outcome=c.status,
                )
            )
        elif c.status in ("cleared", "pending"):
            job = state.employment_of(c.person_id)
            if job is None or job.company_id != c.company_id:
                c = replace(c, status="lapsed", decided_turn=turn)
        out.append(c)
    facilities = []
    live = {f.id for f in state.facilities}
    for f in state.facility_clearances:
        if f.status == "pending" and turn >= f.due_turn:
            f = replace(f, status="cleared")
            logs.append(
                inbox_item(turn, f.company_id, "facility_cleared", facility=str(f.facility_id))
            )
        elif f.status in ("cleared", "pending") and f.facility_id not in live:
            f = replace(f, status="lapsed")
        facilities.append(f)
    new_c, new_f = tuple(out), tuple(facilities)
    if new_c == state.clearances and new_f == state.facility_clearances:
        return state, logs
    return replace(state, clearances=new_c, facility_clearances=new_f), logs
