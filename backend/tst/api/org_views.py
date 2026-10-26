"""Build the M2a org responses from the live state, as seen by the viewing company.

Previews apply the action to the loaded state and report the differences; nothing is
saved and org actions draw no randomness. The morale breakdown hides whatever the company
cannot know (formulas.md 13.11).
"""

from __future__ import annotations

from dataclasses import replace

from tst.api.schemas.org import (
    ChangePreviewOut,
    HiringPlanOut,
    ManagerOut,
    MoraleBreakdownOut,
    MoraleChangeOut,
    MoraleTermOut,
    OrgMemberOut,
    OrgOut,
    PayPreviewOut,
    PlanActivityOut,
    UnitOut,
)
from tst.api.schemas.saves import OrgTileOut
from tst.api.views import person_name, role_label
from tst.loader import LoadedData
from tst.sim.actions import Action, GiveRaise, Promote, apply_action
from tst.sim.actions.org import departments_unlocked, next_level
from tst.sim.calendar import format_turn
from tst.sim.data_models import ORG_TAGS, Balance
from tst.sim.errors import SimError, UnknownPersonError
from tst.sim.hiring.formulas import benefits_cents, monthly_salary_cents, pay_term
from tst.sim.money import BP_DENOMINATOR, Cents
from tst.sim.org.delegates import activity_text, still_needed
from tst.sim.org.formulas import (
    manager_label,
    manager_morale_term,
    manager_quality,
    span_factor,
    span_limit,
    tag_term,
)
from tst.sim.org.models import HiringPlan
from tst.sim.org.morale import market_mid_for, morale_terms
from tst.sim.org.rules import (
    COMMUNICATION,
    LEADERSHIP,
    MENTORING,
    OrgView,
    effective_policy,
    is_remote,
    manager_terms,
    org_view,
    teammate_tag_holders,
)
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

ROOT_KIND = "company"
TAG_TERM_PREFIX = "teammate:"
OTHER = "other"


def org_out(state: GameState, company_id: int, data: LoadedData) -> OrgOut:
    view = org_view(state, company_id)
    company = state.company(company_id)
    leaders = {u.leader_id: u.id for u in view.units.values() if u.leader_id is not None}

    def member(pid: int, unit_id: int | None) -> OrgMemberOut:
        employment = state.employment_of(pid)
        assert employment is not None
        person = state.person(pid)
        return OrgMemberOut(
            person_id=pid,
            name=person_name(person),
            role_label=role_label(employment.role, data) or employment.role,
            level=employment.level,
            is_founder=person.is_founder,
            is_leader=pid == view.leader_of(unit_id),
            manager_id=view.manager_of.get(pid),
            remote=is_remote(state, employment),
        )

    def unit_out(unit_id: int | None) -> UnitOut:
        leader = view.leader_of(unit_id)
        unit = view.units.get(unit_id) if unit_id is not None else None
        product_id = company.root_product_id if unit is None else unit.product_id
        product = None if product_id is None else state.product(product_id)
        return UnitOut(
            unit_id=unit_id,
            kind=ROOT_KIND if unit is None else unit.kind,
            name=company.name if unit is None else unit.name,
            parent_id=None if unit is None else unit.parent_id,
            leader_id=leader,
            leader_name=None if leader is None else person_name(state.person(leader)),
            policy=company.work_policy if unit is None else unit.policy,
            effective_policy=effective_policy(state, company_id, unit_id),
            members=[member(pid, unit_id) for pid in view.members.get(unit_id, ())],
            child_unit_ids=sorted(u.id for u in view.units.values() if u.parent_id == unit_id),
            headcount=_headcount(view, unit_id),
            product_id=product_id,
            product_name=None if product is None else product.name,
        )

    managers = []
    for manager_id, reports in sorted(view.reports.items()):
        leadership = state.person(manager_id).skills[LEADERSHIP]
        limit = span_limit(leadership, data.balance.org)
        term = manager_term(state, view, manager_id, data.balance)
        managers.append(
            ManagerOut(
                person_id=manager_id,
                name=person_name(state.person(manager_id)),
                leads_unit_id=leaders.get(manager_id),
                reports=list(reports),
                span_limit=limit,
                span_factor=span_factor(leadership, len(reports), data.balance.org),
                over_span=len(reports) > limit,
                label=manager_label(term, data.balance.org),
            )
        )
    return OrgOut(
        units=[unit_out(None), *(unit_out(uid) for uid in sorted(view.units))],
        managers=managers,
        headcount=len(state.staff(company_id)),
        departments_unlocked=departments_unlocked(state, company_id, data.balance),
        managers_over_span=sum(1 for m in managers if m.over_span),
    )


def _headcount(view: OrgView, unit_id: int | None) -> int:
    """Members of the unit and of every unit below it (the root counts everyone)."""
    if unit_id is None:
        return sum(len(m) for m in view.members.values())
    below = [u.id for u in view.units.values() if unit_id in view.unit_chain(u.id)]
    return sum(len(view.members.get(u, ())) for u in below)


def manager_term(state: GameState, view: OrgView, manager_id: int, balance: Balance) -> float:
    """The W_mgr a manager gives each direct report (13.3, 13.4)."""
    manager = state.person(manager_id)
    reports = len(view.reports.get(manager_id, ()))
    leadership = manager.skills[LEADERSHIP]
    span = span_factor(leadership, reports, balance.org)
    quality = manager_quality(
        leadership, manager.skills[COMMUNICATION], manager.skills[MENTORING], span
    )
    return manager_morale_term(quality, balance.org)


def org_tile(state: GameState, company_id: int, data: LoadedData) -> OrgTileOut:
    """Units, managers over span, and the label of the average manager term (M2b)."""
    view = org_view(state, company_id)
    org = data.balance.org
    terms = [manager_term(state, view, m, data.balance) for m in sorted(view.reports)]
    over = 0
    for manager_id, reports in view.reports.items():
        limit = span_limit(state.person(manager_id).skills[LEADERSHIP], org)
        over += len(reports) > limit
    return OrgTileOut(
        units=len(view.units),
        managers_over_span=over,
        manager_label=manager_label(sum(terms) / len(terms), org) if terms else None,
    )


# --- Previews -------------------------------------------------------------------------------


def _apply(state: GameState, action: Action, data: LoadedData) -> GameState:
    return apply_action(
        state,
        action,
        RngFactory(state.save_meta.master_seed),
        data.balance,
        data.game_data,
        {},
        seq=0,
    ).new_state


def _energy(state: GameState, actor_id: int) -> int:
    return state.person_state(actor_id).energy or 0


def change_preview(state: GameState, action: Action, data: LoadedData) -> ChangePreviewOut:
    """Energy and the one-off morale change for each person, before an org action."""
    try:
        after = _apply(state, action, data)
    except SimError as exc:
        return ChangePreviewOut(
            allowed=False, problem=exc.message, energy_cost=0, morale_changes=[]
        )
    changes = []
    for e in sorted(state.staff(state.player.id), key=lambda e: e.person_id):
        before = state.person_state(e.person_id).morale
        now = after.person_state(e.person_id).morale
        if before is not None and now is not None and now != before:
            changes.append(
                MoraleChangeOut(
                    person_id=e.person_id,
                    name=person_name(state.person(e.person_id)),
                    change=now - before,
                )
            )
    return ChangePreviewOut(
        allowed=True,
        problem=None,
        energy_cost=_energy(state, action.actor_id) - _energy(after, action.actor_id),
        morale_changes=changes,
    )


def pay_preview(state: GameState, action: GiveRaise | Promote, data: LoadedData) -> PayPreviewOut:
    """New salary and level against the market rate, and the one-off morale (13.8)."""
    employment = state.employment_of(action.person_id)
    if employment is None or employment.company_id != state.player.id:
        raise UnknownPersonError(f"person {action.person_id} is not on staff")
    person = state.person(action.person_id)
    if person.is_founder:
        return _pay_out(state, state, action, data, "the founder's pay and level do not change")
    try:
        after = _apply(state, action, data)
    except SimError as exc:
        return _pay_out(state, state, action, data, exc.message)
    return _pay_out(state, after, action, data, None)


def _pay_out(
    before: GameState,
    after: GameState,
    action: GiveRaise | Promote,
    data: LoadedData,
    problem: str | None,
) -> PayPreviewOut:
    old = before.employment_of(action.person_id)
    assert old is not None
    new = after.employment_of(action.person_id) or old
    person = before.person(action.person_id)
    morale_cfg = data.balance.morale
    if problem is not None:
        # Show what the change would be even when it is refused.
        salary = action.salary_cents if isinstance(action, GiveRaise) else old.salary_cents
        level = (next_level(old.level) or old.level) if isinstance(action, Promote) else old.level
    else:
        salary, level = new.salary_cents, new.level
    founder = person.is_founder
    market = 0 if founder else market_mid_for(old, person.region, data.game_data)
    new_market = (
        0 if founder else market_mid_for(replace(old, level=level), person.region, data.game_data)
    )
    morale_before = before.person_state(action.person_id).morale
    morale_after = after.person_state(action.person_id).morale
    old_salary = old.salary_cents

    def monthly(salary: int) -> int:
        month = monthly_salary_cents(salary)
        return month + benefits_cents(month, data.balance.payroll)

    return PayPreviewOut(
        allowed=problem is None,
        problem=problem,
        energy_cost=_energy(before, action.actor_id) - _energy(after, action.actor_id),
        level=old.level,
        new_level=level,
        salary_cents=old.salary_cents,
        new_salary_cents=salary,
        market_rate_cents=market,
        new_market_rate_cents=new_market,
        pay_term=0.0 if founder else pay_term(old.salary_cents, market, morale_cfg),
        new_pay_term=0.0 if founder else pay_term(salary, new_market, morale_cfg),
        salary_change_bp=0
        if old_salary == 0
        else round((salary - old_salary) * BP_DENOMINATOR / old_salary),
        market_ratio=0.0 if not market else old_salary / market,
        new_market_ratio=0.0 if not new_market else salary / new_market,
        monthly_cost_change_cents=monthly(salary) - monthly(old_salary),
        below_market=not founder and salary < new_market,
        morale_change=0.0
        if morale_before is None or morale_after is None
        else morale_after - morale_before,
    )


# --- Hiring plans ---------------------------------------------------------------------------


def plan_out(state: GameState, plan: HiringPlan, data: LoadedData) -> HiringPlanOut:
    unit = state.unit(plan.unit_id) if plan.unit_id is not None else None
    label = role_label(plan.role, data) or plan.role
    activity = plan.last_activity
    pending = plan.target - plan.hired - still_needed(state, plan)
    return HiringPlanOut(
        plan_id=plan.id,
        owner_id=plan.owner_id,
        owner_name=person_name(state.person(plan.owner_id)),
        owner_role_label=role_label(state.person(plan.owner_id).role, data) or "",
        owner_on_staff=_on_staff(state, plan),
        unit_id=plan.unit_id,
        unit_name=state.company(plan.company_id).name if unit is None else unit.name,
        role=plan.role,
        role_label=label,
        target=plan.target,
        hired=plan.hired,
        pending_offers=pending,
        channel=plan.channel,
        ratio_bp=plan.ratio_bp,
        equity_bp=plan.equity_bp,
        focus=plan.focus,
        status=plan.status,
        created_turn=plan.created_turn,
        owner_energy=state.person_state(plan.owner_id).energy,
        last_activity=None
        if activity is None
        else PlanActivityOut(
            turn=activity.turn,
            date_label=format_turn(activity.turn),
            searches=activity.searches,
            interviews=activity.interviews,
            scouted=activity.scouted,
            offers=activity.offers,
            summary=activity_text(activity, label.lower(), plan.focus),
        ),
    )


def _on_staff(state: GameState, plan: HiringPlan) -> bool:
    employment = state.employment_of(plan.owner_id)
    return employment is not None and employment.company_id == plan.company_id


# --- Morale breakdown -----------------------------------------------------------------------


def morale_breakdown(
    state: GameState,
    company_id: int,
    person_id: int,
    data: LoadedData,
    cash_cents: Cents,
    projected_costs_cents: Cents,
) -> MoraleBreakdownOut:
    """This month's morale target as the company can see it (formulas.md 13.11).

    Runway uses this month's projected costs, as on the Overview. Fit is shown once the
    profile is known; teammate tags only for holders the company has noticed. Everything
    else sums into "other".
    """
    employment = state.employment_of(person_id)
    person = state.person(person_id) if employment is not None else None
    if employment is None or employment.company_id != company_id or person is None:
        raise UnknownPersonError(f"person {person_id} is not on staff")
    if person.is_founder:
        raise UnknownPersonError("the founder has no morale")
    view = org_view(state, company_id)
    terms = morale_terms(
        state,
        view,
        employment,
        data.balance,
        data.game_data,
        cash_cents,
        cash_cents - projected_costs_cents,
    )
    reveal = state.reveal(company_id, person_id)
    profile_known = reveal is not None and reveal.profile_revealed_turn is not None
    shown: list[MoraleTermOut] = [
        MoraleTermOut(key="base", label="Baseline", value=terms.base),
        MoraleTermOut(key="pay", label="Pay against the market rate", value=terms.pay),
    ]
    if profile_known:
        shown.append(MoraleTermOut(key="fit", label="Mission and work-style fit", value=terms.fit))
    shown += [
        MoraleTermOut(key="runway", label="Cash runway", value=terms.runway),
        MoraleTermOut(key="manager", label="Their manager", value=terms.manager),
        MoraleTermOut(key="remote", label="Work-location policy", value=terms.remote),
    ]
    holders = teammate_tag_holders(state, view, person_id)
    labels = {t.key: t.label for t in data.game_data.tags}
    for tag in ORG_TAGS:
        noticed = [p for p in holders[tag] if _noticed(state, company_id, p, tag)]
        if noticed:
            shown.append(
                MoraleTermOut(
                    key=f"{TAG_TERM_PREFIX}{tag}",
                    label=f"Teammates: {labels[tag].lower()}",
                    value=tag_term(tag, len(noticed), data.balance.org),
                )
            )
    other = terms.target - sum(t.value for t in shown)
    shown.append(MoraleTermOut(key=OTHER, label="Other", value=round(other, 9) + 0.0))
    manager = manager_terms(state, view, person_id, data.balance).manager_id
    ps = state.person_state(person_id)
    return MoraleBreakdownOut(
        person_id=person_id,
        morale=ps.morale if ps.morale is not None else data.balance.morale.new_hire,
        target=terms.target,
        rate=data.balance.morale.rate,
        terms=shown,
        manager_id=manager,
        manager_name=None if manager is None else person_name(state.person(manager)),
    )


def _noticed(state: GameState, company_id: int, person_id: int, tag: str) -> bool:
    reveal = state.reveal(company_id, person_id)
    return reveal is not None and tag in {t for t, _ in reveal.revealed_tags}
