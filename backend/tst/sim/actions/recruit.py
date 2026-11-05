"""Replace (docs/formulas.md 29.5, M14b): when someone resigns or is poached and a recruiter
is on staff, one action opens a recruiter-led plan for one hire with the leaver's role and
level, joining their unit, and opens its search at once. Its candidates arrive screened and
the recruiter offers in the month they arrive (hiring.recruit.replace_offers)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import OpenSearch, Outcome, acting_company, open_search, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.hiring.recruit import leaver, recruiter_on_staff, replace_problem
from tst.sim.ledger import LedgerBalances
from tst.sim.log import inbox_item
from tst.sim.org.models import HiringPlan
from tst.sim.state import GameState, with_person_state, with_plan

PLAN_CHANNEL: Final = "recruiter"


@dataclass(frozen=True, slots=True)
class ReplaceLeaver:
    actor_id: int
    person_id: int  # who resigned or was poached
    kind: Literal["replace_leaver"] = "replace_leaver"


def replace_leaver(
    state: GameState,
    action: ReplaceLeaver,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    founder = state.founder_of(company)
    if founder is None or founder.id != action.actor_id:
        raise InvalidActionError("only the founder starts a Replace")
    problem = replace_problem(state, company, action.person_id, balance)
    if problem:
        raise InvalidActionError(problem)
    left = leaver(state, company, action.person_id)
    recruiter = recruiter_on_staff(state, company)
    assert left is not None and recruiter is not None
    state = spend_energy(state, action.actor_id, "hiring_plan", balance)
    unit = left.unit_id if left.unit_id is not None and state.unit(left.unit_id) else None
    plan_id, ids = state.next_ids.take("plan")
    plan = HiringPlan(
        id=plan_id,
        company_id=company,
        owner_id=recruiter,
        unit_id=unit,
        role=left.role,
        target=1,
        channel=PLAN_CHANNEL,
        ratio_bp=balance.recruit.replace_ratio_bp,
        equity_bp=0,
        created_turn=state.turn,
        replace_of=action.person_id,
        level=left.level,
    )
    state = with_plan(replace(state, next_ids=ids), plan)
    ps = state.person_state(recruiter)
    if ps.energy is None:
        state = with_person_state(state, replace(ps, energy=balance.delegates.energy_per_month))
    search = OpenSearch(recruiter, left.role, PLAN_CHANNEL, plan_id=plan_id, level=left.level)
    opened = open_search(state, search, balance, data, balances)
    person = state.person(action.person_id)
    log = inbox_item(
        state.turn,
        company,
        "replace_started",
        link_kind="person",
        link_id=recruiter,
        name=f"{person.first_name} {person.last_name}",
        role=data.role(left.role).label,
    )
    return Outcome(opened.state, opened.entries, (log,))
