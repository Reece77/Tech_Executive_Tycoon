"""Organization actions (ADR-0014): units, leaders, moves, policies, raises, promotions and
hiring plans (docs/formulas.md section 13). They take effect at once.

One-off morale changes (13.7, 13.8) apply to employees' current morale; the founder has none.
Every rule of 13.1 that an action could break raises `OrgRuleError`, changing nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, judgment, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import (
    InvalidActionError,
    OrgRuleError,
    UnknownPersonError,
    UnknownPlanError,
    UnknownRoleError,
    UnknownUnitError,
)
from tst.sim.org.formulas import is_raise_bonus
from tst.sim.org.models import (
    PLAN_CHANNELS,
    PLAN_FOCUSES,
    UNIT_KINDS,
    WORK_POLICIES,
    HiringPlan,
    OrgUnit,
    PlanChannel,
    PlanFocus,
    PlanStatus,
    UnitKind,
    WorkPolicy,
)
from tst.sim.org.upkeep import release_job_posts
from tst.sim.people.models import Employment
from tst.sim.people.reveal import apply_knowledge_action
from tst.sim.scale import clamp_morale
from tst.sim.state import (
    GameState,
    with_company,
    with_employment,
    with_offer,
    with_person_state,
    with_plan,
    with_reveal,
    with_search,
    with_unit,
)

DEPARTMENT_STAGE: Final = 2  # spec section 6: departments unlock at stage 2 (or 10 staff, 13.1)
UNIT_NAME_MAX: Final = 64  # tunable-exempt: org_unit.name column width
PROMOTION_LADDER: Final = ("junior", "mid", "senior", "staff", "principal")  # 13.8; no exec


# --- Action types ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreateUnit:
    actor_id: int
    unit_kind: UnitKind
    name: str
    parent_id: int | None = None  # None = the company root
    kind: Literal["create_unit"] = "create_unit"


@dataclass(frozen=True, slots=True)
class DissolveUnit:
    actor_id: int
    unit_id: int
    kind: Literal["dissolve_unit"] = "dissolve_unit"


@dataclass(frozen=True, slots=True)
class RenameUnit:
    """Rename a department or team (free; no morale change)."""

    actor_id: int
    unit_id: int
    name: str
    kind: Literal["rename_unit"] = "rename_unit"


@dataclass(frozen=True, slots=True)
class MoveUnit:
    """Re-parent a team under a department or the company root (13.1, 13.7)."""

    actor_id: int
    unit_id: int
    parent_id: int | None  # a department, or None for the company root
    kind: Literal["move_unit"] = "move_unit"


@dataclass(frozen=True, slots=True)
class SetLeader:
    actor_id: int
    unit_id: int
    person_id: int | None  # None removes the current leader
    kind: Literal["set_leader"] = "set_leader"


@dataclass(frozen=True, slots=True)
class MovePerson:
    actor_id: int
    person_id: int
    unit_id: int | None  # None = the company root
    kind: Literal["move_person"] = "move_person"


@dataclass(frozen=True, slots=True)
class SetPolicy:
    actor_id: int
    unit_id: int | None  # None = the company root
    policy: WorkPolicy | None  # None = inherit the parent's (not allowed for the root)
    kind: Literal["set_policy"] = "set_policy"


@dataclass(frozen=True, slots=True)
class GiveRaise:
    actor_id: int
    person_id: int
    salary_cents: int  # the new annual salary
    kind: Literal["give_raise"] = "give_raise"


@dataclass(frozen=True, slots=True)
class Promote:
    actor_id: int
    person_id: int
    kind: Literal["promote"] = "promote"


@dataclass(frozen=True, slots=True)
class CreatePlan:
    actor_id: int
    owner_id: int
    role: str
    target: int
    channel: PlanChannel
    ratio_bp: int
    equity_bp: int = 0
    unit_id: int | None = None
    focus: PlanFocus = "current"
    kind: Literal["create_plan"] = "create_plan"


@dataclass(frozen=True, slots=True)
class UpdatePlan:
    """Every editable field of a plan, as it should be after the change."""

    actor_id: int
    plan_id: int
    owner_id: int
    role: str
    target: int
    channel: PlanChannel
    ratio_bp: int
    equity_bp: int
    unit_id: int | None
    focus: PlanFocus = "current"  # default keeps M2a decision logs loadable
    kind: Literal["update_plan"] = "update_plan"


@dataclass(frozen=True, slots=True)
class ClosePlan:
    actor_id: int
    plan_id: int
    kind: Literal["close_plan"] = "close_plan"


@dataclass(frozen=True, slots=True)
class Scout:
    """scouting_month (formulas.md 4) on every open candidate for a role (13.10 step 4)."""

    actor_id: int
    role: str
    kind: Literal["scout"] = "scout"


type OrgAction = (
    CreateUnit
    | DissolveUnit
    | MoveUnit
    | RenameUnit
    | SetLeader
    | MovePerson
    | SetPolicy
    | GiveRaise
    | Promote
    | CreatePlan
    | UpdatePlan
    | ClosePlan
    | Scout
)


# --- Shared steps ---------------------------------------------------------------------------


def bump_morale(state: GameState, person_id: int, delta: float) -> GameState:
    """A one-off morale change for an employee; the founder (no morale) is unaffected."""
    ps = state.person_state(person_id)
    if ps.morale is None or delta == 0:
        return state
    return with_person_state(state, replace(ps, morale=clamp_morale(ps.morale + delta)))


def active_unit(state: GameState, company_id: int, unit_id: int) -> OrgUnit:
    unit = state.unit(unit_id)
    if unit is None or unit.company_id != company_id or unit.status != "active":
        raise UnknownUnitError(f"no unit {unit_id}")
    return unit


def staff_employment(state: GameState, company_id: int, person_id: int) -> Employment:
    employment = state.employment_of(person_id)
    if employment is None or employment.company_id != company_id:
        raise UnknownPersonError(f"person {person_id} is not on staff")
    return employment


def employee(state: GameState, company_id: int, person_id: int, what: str) -> Employment:
    """A staff member other than the founder (who cannot be moved, led, raised or promoted)."""
    employment = staff_employment(state, company_id, person_id)
    if state.person(person_id).is_founder:
        raise OrgRuleError(f"the founder cannot {what}")
    return employment


def members(state: GameState, unit_id: int) -> tuple[Employment, ...]:
    return tuple(
        e
        for e in sorted(state.employments, key=lambda e: e.person_id)
        if e.counts_as_staff and e.unit_id == unit_id
    )


def led_unit(state: GameState, person_id: int) -> OrgUnit | None:
    for unit in state.units:
        if unit.status == "active" and unit.leader_id == person_id:
            return unit
    return None


def departments_unlocked(state: GameState, company_id: int, balance: Balance) -> bool:
    """Departments unlock at 10 staff, or at stage 2 (formulas.md 13.1)."""
    company = state.company(company_id)
    headcount = len(state.staff(company_id))
    return headcount >= balance.org.department_unlock_headcount or company.stage >= DEPARTMENT_STAGE


def _clean_name(state: GameState, company_id: int, name: str, keep: int | None = None) -> str:
    cleaned = " ".join(name.split())
    if not cleaned:
        raise OrgRuleError("a unit needs a name")
    if len(cleaned) > UNIT_NAME_MAX:
        raise OrgRuleError(f"a unit name may have at most {UNIT_NAME_MAX} characters")
    taken = {u.name.casefold() for u in state.active_units(company_id) if u.id != keep}
    if cleaned.casefold() in taken:
        raise OrgRuleError(f"there is already a unit named {cleaned!r}")
    return cleaned


# --- Units ----------------------------------------------------------------------------------


def create_unit(state: GameState, action: CreateUnit, balance: Balance) -> Outcome:
    company = acting_company(state, action.actor_id)
    if action.unit_kind not in UNIT_KINDS:
        raise OrgRuleError(f"unknown unit kind {action.unit_kind!r}")
    name = _clean_name(state, company, action.name)
    if action.unit_kind == "department":
        if action.parent_id is not None:
            raise OrgRuleError("a department sits directly under the company")
        if not departments_unlocked(state, company, balance):
            raise OrgRuleError(
                f"departments unlock at {balance.org.department_unlock_headcount} staff "
                "or once the company is venture-backed"
            )
    elif action.parent_id is not None:
        parent = active_unit(state, company, action.parent_id)
        if parent.kind != "department":
            raise OrgRuleError("a team sits under the company or a department, not a team")
    state = spend_energy(state, action.actor_id, "create_unit", balance)
    unit_id, ids = state.next_ids.take("unit")
    unit = OrgUnit(
        id=unit_id,
        company_id=company,
        kind=action.unit_kind,
        name=name,
        parent_id=action.parent_id,
        leader_id=None,
        policy=None,
        created_turn=state.turn,
    )
    return Outcome(replace(with_unit(state, unit), next_ids=ids))


def dissolve_unit(state: GameState, action: DissolveUnit, balance: Balance) -> Outcome:
    """Members and child teams move to the parent; each member loses morale (13.7)."""
    company = acting_company(state, action.actor_id)
    unit = active_unit(state, company, action.unit_id)
    state = spend_energy(state, action.actor_id, "dissolve_unit", balance)
    parent = unit.parent_id
    for e in members(state, unit.id):
        state = with_employment(state, replace(e, unit_id=parent))
        state = bump_morale(state, e.person_id, balance.org.reorg.dissolve_members)
    for child in state.active_units(company):
        if child.parent_id == unit.id:
            state = with_unit(state, replace(child, parent_id=parent))
    for plan in state.live_plans(company):
        if plan.unit_id == unit.id:
            state = with_plan(state, replace(plan, unit_id=parent))
    for offer in state.pending_offers(company):
        if offer.unit_id == unit.id:
            state = with_offer(state, replace(offer, unit_id=parent))
    dissolved = replace(unit, status="dissolved", dissolved_turn=state.turn, leader_id=None)
    return Outcome(with_unit(state, dissolved))


def rename_unit(state: GameState, action: RenameUnit) -> Outcome:
    company = acting_company(state, action.actor_id)
    unit = active_unit(state, company, action.unit_id)
    name = _clean_name(state, company, action.name, keep=unit.id)
    if name == unit.name:
        raise OrgRuleError(f"the unit is already named {name!r}")
    return Outcome(with_unit(state, replace(unit, name=name)))


def move_unit(state: GameState, action: MoveUnit, balance: Balance) -> Outcome:
    """A team moves with its members and leader; nobody's morale changes (13.7)."""
    company = acting_company(state, action.actor_id)
    unit = active_unit(state, company, action.unit_id)
    if unit.kind != "team":
        raise OrgRuleError("only teams move; a department sits directly under the company")
    if action.parent_id is not None:
        parent = active_unit(state, company, action.parent_id)
        if parent.kind != "department":
            raise OrgRuleError("a team sits under the company or a department, not a team")
    if unit.parent_id == action.parent_id:
        raise OrgRuleError(f"{unit.name} is already there")
    state = spend_energy(state, action.actor_id, "move_unit", balance)
    return Outcome(with_unit(state, replace(unit, parent_id=action.parent_id)))


def set_leader(state: GameState, action: SetLeader, balance: Balance) -> Outcome:
    """Any change of leader: -1 for each other member, -5 for the leader who loses the post."""
    company = acting_company(state, action.actor_id)
    unit = active_unit(state, company, action.unit_id)
    old = unit.leader_id
    new = action.person_id
    if new is None:
        if old is None:
            raise OrgRuleError(f"{unit.name} has no leader to remove")
    else:
        employment = employee(state, company, new, "lead a unit")
        if new == old:
            raise OrgRuleError("they already lead this unit")
        if employment.unit_id != unit.id:
            raise OrgRuleError(f"a leader must be a member of the unit; move them to {unit.name}")
        if led_unit(state, new) is not None:
            raise OrgRuleError("a person leads at most one unit")
    state = spend_energy(state, action.actor_id, "set_leader", balance)
    reorg = balance.org.reorg
    for e in members(state, unit.id):
        if e.person_id == new:
            continue
        delta = reorg.replaced_leader if e.person_id == old else reorg.new_leader_members
        state = bump_morale(state, e.person_id, delta)
    return Outcome(with_unit(state, replace(unit, leader_id=new)))


def move_person(state: GameState, action: MovePerson, balance: Balance) -> Outcome:
    company = acting_company(state, action.actor_id)
    employment = employee(state, company, action.person_id, "leave the company root")
    if action.unit_id is not None:
        active_unit(state, company, action.unit_id)
    if employment.unit_id == action.unit_id:
        raise OrgRuleError("they are already in that unit")
    leads = led_unit(state, action.person_id)
    if leads is not None:
        raise OrgRuleError(f"they lead {leads.name}; replace or remove them as leader first")
    state = spend_energy(state, action.actor_id, "move_person", balance)
    state = with_employment(state, replace(employment, unit_id=action.unit_id))
    return Outcome(bump_morale(state, action.person_id, balance.org.reorg.move))


def set_policy(state: GameState, action: SetPolicy, balance: Balance) -> Outcome:
    company_id = acting_company(state, action.actor_id)
    if action.policy is not None and action.policy not in WORK_POLICIES:
        raise OrgRuleError(f"unknown work-location policy {action.policy!r}")
    if action.unit_id is None:
        company = state.company(company_id)
        if action.policy is None:
            raise OrgRuleError("the company has no parent to inherit a policy from")
        if company.work_policy == action.policy:
            raise OrgRuleError(f"the company policy is already {action.policy}")
        state = spend_energy(state, action.actor_id, "set_policy", balance)
        return Outcome(with_company(state, replace(company, work_policy=action.policy)))
    unit = active_unit(state, company_id, action.unit_id)
    if unit.policy == action.policy:
        raise OrgRuleError(f"{unit.name} already has that policy")
    state = spend_energy(state, action.actor_id, "set_policy", balance)
    return Outcome(with_unit(state, replace(unit, policy=action.policy)))


# --- Pay and level --------------------------------------------------------------------------


def raise_morale_change(
    employment: Employment, salary_cents: int, turn: int, balance: Balance
) -> float:
    """+3 for a raise of at least 5% (once per 12 turns), -10 for any cut, else 0 (13.8)."""
    org = balance.org
    if salary_cents < employment.salary_cents:
        return org.pay_cut_morale
    cooled = (
        employment.last_raise_turn is None
        or turn - employment.last_raise_turn >= org.raise_cooldown_turns
    )
    if cooled and is_raise_bonus(employment.salary_cents, salary_cents, org):
        return org.raise_morale
    return 0.0


def give_raise(state: GameState, action: GiveRaise, balance: Balance) -> Outcome:
    """The new salary applies from the next payroll (phase 6)."""
    company = acting_company(state, action.actor_id)
    employment = employee(state, company, action.person_id, "be given a raise")
    if action.salary_cents <= 0:
        raise InvalidActionError("salary must be positive")
    if action.salary_cents == employment.salary_cents:
        raise InvalidActionError("that is their current salary")
    state = spend_energy(state, action.actor_id, "give_raise", balance)
    change = raise_morale_change(employment, action.salary_cents, state.turn, balance)
    last = state.turn if change > 0 else employment.last_raise_turn
    state = with_employment(
        state, replace(employment, salary_cents=action.salary_cents, last_raise_turn=last)
    )
    return Outcome(bump_morale(state, action.person_id, change))


def next_level(level: str) -> str | None:
    if level not in PROMOTION_LADDER:
        return None
    index = PROMOTION_LADDER.index(level)
    return PROMOTION_LADDER[index + 1] if index + 1 < len(PROMOTION_LADDER) else None


def promote(state: GameState, action: Promote, balance: Balance) -> Outcome:
    """One level up; the new level's market rate applies from now on (13.8)."""
    company = acting_company(state, action.actor_id)
    employment = employee(state, company, action.person_id, "be promoted")
    level = next_level(employment.level)
    if level is None:
        raise InvalidActionError(f"{employment.level} is the highest level a promotion reaches")
    state = spend_energy(state, action.actor_id, "promote", balance)
    state = with_employment(state, replace(employment, level=level))
    return Outcome(bump_morale(state, action.person_id, balance.org.promote_morale))


# --- Hiring plans ---------------------------------------------------------------------------


def _check_plan(
    state: GameState,
    company: int,
    owner_id: int,
    role: str,
    target: int,
    channel: str,
    ratio_bp: int,
    equity_bp: int,
    unit_id: int | None,
    focus: str,
    balance: Balance,
    data: GameData,
) -> None:
    employee(state, company, owner_id, "own a hiring plan (it needs a delegate)")
    if focus not in PLAN_FOCUSES:
        raise InvalidActionError(f"unknown focus {focus!r}")
    if role not in {r.key for r in data.roles}:
        raise UnknownRoleError(f"unknown role {role!r}")
    if target < 1:
        raise InvalidActionError("a plan needs a target of at least one hire")
    if channel not in PLAN_CHANNELS:
        raise InvalidActionError(f"unknown channel {channel!r}")
    max_ratio = balance.delegates.max_ratio_bp
    if not 0 < ratio_bp <= max_ratio:
        raise InvalidActionError(f"the salary ratio must be above 0 and at most {max_ratio} bp")
    if not 0 <= equity_bp <= balance.hiring.max_offer_equity_bp:
        raise InvalidActionError(
            f"equity per offer must be 0 to {balance.hiring.max_offer_equity_bp} bp"
        )
    if unit_id is not None:
        active_unit(state, company, unit_id)


def _with_delegate_energy(state: GameState, owner_id: int, balance: Balance) -> GameState:
    """A new delegate starts tracking energy (13.10)."""
    ps = state.person_state(owner_id)
    if ps.energy is not None:
        return state
    return with_person_state(state, replace(ps, energy=balance.delegates.energy_per_month))


def create_plan(state: GameState, action: CreatePlan, balance: Balance, data: GameData) -> Outcome:
    company = acting_company(state, action.actor_id)
    _check_plan(
        state,
        company,
        action.owner_id,
        action.role,
        action.target,
        action.channel,
        action.ratio_bp,
        action.equity_bp,
        action.unit_id,
        action.focus,
        balance,
        data,
    )
    state = spend_energy(state, action.actor_id, "hiring_plan", balance)
    state = _with_delegate_energy(state, action.owner_id, balance)
    plan_id, ids = state.next_ids.take("plan")
    plan = HiringPlan(
        id=plan_id,
        company_id=company,
        owner_id=action.owner_id,
        unit_id=action.unit_id,
        role=action.role,
        target=action.target,
        channel=action.channel,
        ratio_bp=action.ratio_bp,
        equity_bp=action.equity_bp,
        created_turn=state.turn,
        focus=action.focus,
    )
    return Outcome(replace(with_plan(state, plan), next_ids=ids))


def live_plan(state: GameState, company_id: int, plan_id: int) -> HiringPlan:
    plan = state.plan(plan_id)
    if plan is None or plan.company_id != company_id or plan.status == "closed":
        raise UnknownPlanError(f"no hiring plan {plan_id}")
    return plan


def update_plan(state: GameState, action: UpdatePlan, balance: Balance, data: GameData) -> Outcome:
    """A paused plan with an owner on staff, or a filled plan with room, becomes active."""
    company = acting_company(state, action.actor_id)
    plan = live_plan(state, company, action.plan_id)
    _check_plan(
        state,
        company,
        action.owner_id,
        action.role,
        action.target,
        action.channel,
        action.ratio_bp,
        action.equity_bp,
        action.unit_id,
        action.focus,
        balance,
        data,
    )
    state = spend_energy(state, action.actor_id, "hiring_plan", balance)
    state = _with_delegate_energy(state, action.owner_id, balance)
    status: PlanStatus = "active" if plan.hired < action.target else "filled"
    updated = replace(
        plan,
        owner_id=action.owner_id,
        role=action.role,
        target=action.target,
        channel=action.channel,
        ratio_bp=action.ratio_bp,
        equity_bp=action.equity_bp,
        unit_id=action.unit_id,
        status=status,
        focus=action.focus,
    )
    return Outcome(with_plan(state, updated))


def close_plan(state: GameState, action: ClosePlan) -> Outcome:
    """Free, like closing a search. Offers already made still resolve. The job posts the
    plan opened close too, unless another open plan for the role uses them (13.10)."""
    company = acting_company(state, action.actor_id)
    plan = live_plan(state, company, action.plan_id)
    closed = replace(plan, status="closed", closed_turn=state.turn)
    state, to_close = release_job_posts(with_plan(state, closed), closed)
    for search in to_close:
        state = with_search(state, replace(search, status="closed", closed_turn=state.turn))
    return Outcome(state)


def scout(state: GameState, action: Scout, balance: Balance, data: GameData) -> Outcome:
    company = acting_company(state, action.actor_id)
    targets = [
        c for c in state.open_candidates(company) if state.person(c.person_id).role == action.role
    ]
    if not targets:
        raise InvalidActionError(f"no open candidates for {action.role} to scout")
    state = spend_energy(
        state, action.actor_id, "scout", balance, cost=balance.delegates.scout_cost
    )
    scout_judgment = judgment(state.person(action.actor_id))
    skill_keys = frozenset(data.skill_keys)
    for candidate in targets:
        reveal = state.reveal(company, candidate.person_id)
        if reveal is None:
            continue
        state = with_reveal(
            state,
            apply_knowledge_action(
                reveal,
                "scouting_month",
                scout_judgment,
                balance,
                turn=state.turn,
                skill_keys=skill_keys,
            ),
        )
    return Outcome(state)
