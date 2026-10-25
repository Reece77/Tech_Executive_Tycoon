"""Reporting lines and the org terms of morale, growth and office cost (formulas.md 13).

Everything here is derived from the state; nothing is stored. `org_view` resolves one
company's reporting lines once, so a phase can look up managers and teammates cheaply.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from tst.sim.data_models import MENTOR_TAG, ORG_TAGS, Balance
from tst.sim.org.formulas import (
    growth_multiplier,
    manager_morale_term,
    manager_quality,
    remote_term,
    span_factor,
    span_limit,
    tag_term,
)
from tst.sim.org.models import OrgUnit, WorkPolicy
from tst.sim.people.models import Employment
from tst.sim.state import GameState

LEADERSHIP = "leadership"
COMMUNICATION = "communication"
MENTORING = "mentoring"
SOCIABILITY = "sociability"


@dataclass(frozen=True, slots=True)
class OrgView:
    """One company's reporting lines. Unit id None is the company root."""

    company_id: int
    founder_id: int | None
    units: Mapping[int, OrgUnit]  # active units by id
    unit_of: Mapping[int, int | None]  # staff person id -> unit id
    members: Mapping[int | None, tuple[int, ...]]  # unit id -> member ids, ascending
    manager_of: Mapping[int, int | None]  # staff person id -> manager id (None: founder)
    reports: Mapping[int, tuple[int, ...]]  # manager id -> direct report ids, ascending

    def unit_chain(self, unit_id: int | None) -> tuple[int, ...]:
        """The unit and its ancestors, innermost first (the root is not listed)."""
        chain = []
        while unit_id is not None and unit_id in self.units and unit_id not in chain:
            chain.append(unit_id)
            unit_id = self.units[unit_id].parent_id
        return tuple(chain)

    def leader_of(self, unit_id: int | None) -> int | None:
        """The unit's leader; the root's leader is the founder (13.1)."""
        if unit_id is None:
            return self.founder_id
        return self.units[unit_id].leader_id


def org_view(state: GameState, company_id: int) -> OrgView:
    staff = sorted(state.staff(company_id), key=lambda e: e.person_id)
    founder = state.founder_of(company_id)
    founder_id = founder.id if founder else None
    units = {u.id: u for u in state.active_units(company_id)}
    unit_of: dict[int, int | None] = {}
    members: dict[int | None, list[int]] = defaultdict(list)
    for e in staff:
        unit = e.unit_id if e.unit_id in units and e.person_id != founder_id else None
        unit_of[e.person_id] = unit
        members[unit].append(e.person_id)
    on_staff = set(unit_of)
    manager_of: dict[int, int | None] = {}
    reports: dict[int, list[int]] = defaultdict(list)
    for e in staff:
        manager = _resolve_manager(e.person_id, unit_of, units, founder_id, on_staff)
        manager_of[e.person_id] = manager
        if manager is not None:
            reports[manager].append(e.person_id)
    return OrgView(
        company_id=company_id,
        founder_id=founder_id,
        units=units,
        unit_of=unit_of,
        members={k: tuple(v) for k, v in members.items()},
        manager_of=manager_of,
        reports={k: tuple(v) for k, v in reports.items()},
    )


def _resolve_manager(
    person_id: int,
    unit_of: Mapping[int, int | None],
    units: Mapping[int, OrgUnit],
    founder_id: int | None,
    on_staff: set[int],
) -> int | None:
    """The unit's leader; leaders and members of leaderless units look one level up (13.1)."""
    if person_id == founder_id:
        return None
    unit_id = unit_of[person_id]
    seen: set[int] = set()
    while unit_id is not None and unit_id not in seen:
        seen.add(unit_id)
        unit = units[unit_id]
        leader = unit.leader_id
        if leader is not None and leader != person_id and leader in on_staff:
            return leader
        unit_id = unit.parent_id if unit.parent_id in units else None
    return founder_id


# --- Policies -------------------------------------------------------------------------------


def effective_policy(state: GameState, company_id: int, unit_id: int | None) -> WorkPolicy:
    """A unit's own policy, else its parent's, up to the company root (13.9)."""
    seen: set[int] = set()
    while unit_id is not None and unit_id not in seen:
        seen.add(unit_id)
        unit = state.unit(unit_id)
        if unit is None or unit.status != "active":
            break
        if unit.policy is not None:
            return unit.policy
        unit_id = unit.parent_id
    return state.company(company_id).work_policy


def is_remote(state: GameState, employment: Employment) -> bool:
    return effective_policy(state, employment.company_id, employment.unit_id) == "remote"


# --- Terms for one person ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ManagerTerms:
    manager_id: int | None
    reports: int  # the manager's direct reports
    span_limit: int
    span: float  # S
    quality: float  # Q
    morale: float  # W_mgr
    growth: float  # M_growth


def span_of(state: GameState, view: OrgView, manager_id: int, balance: Balance) -> float:
    leadership = state.person(manager_id).skills[LEADERSHIP]
    return span_factor(leadership, len(view.reports.get(manager_id, ())), balance.org)


def manager_terms(
    state: GameState, view: OrgView, person_id: int, balance: Balance
) -> ManagerTerms:
    """W_mgr and M_growth from the person's manager's true skills (13.3-13.5).

    The founder has no manager: both terms are neutral (0 and 1).
    """
    org = balance.org
    manager_id = view.manager_of.get(person_id)
    if manager_id is None:
        return ManagerTerms(None, 0, 0, 1.0, 0.0, 0.0, 1.0)
    manager = state.person(manager_id)
    n = len(view.reports.get(manager_id, ()))
    leadership = manager.skills[LEADERSHIP]
    s = span_factor(leadership, n, org)
    q = manager_quality(leadership, manager.skills[COMMUNICATION], manager.skills[MENTORING], s)
    return ManagerTerms(
        manager_id=manager_id,
        reports=n,
        span_limit=span_limit(leadership, org),
        span=s,
        quality=q,
        morale=manager_morale_term(q, org),
        growth=growth_multiplier(
            manager.skills[MENTORING], s, has_teammate_tag(state, view, person_id, MENTOR_TAG), org
        ),
    )


def teammates(view: OrgView, person_id: int) -> tuple[int, ...]:
    """The other members of the person's unit."""
    unit = view.unit_of.get(person_id)
    return tuple(p for p in view.members.get(unit, ()) if p != person_id)


def has_teammate_tag(state: GameState, view: OrgView, person_id: int, tag: str) -> bool:
    return any(tag in state.person(p).tags for p in teammates(view, person_id))


def teammate_tag_holders(state: GameState, view: OrgView, person_id: int) -> dict[str, list[int]]:
    """For each morale tag (13.6), the other members of the unit who truly hold it."""
    holders: dict[str, list[int]] = {tag: [] for tag in ORG_TAGS}
    for other in teammates(view, person_id):
        for tag in state.person(other).tags:
            if tag in holders:
                holders[tag].append(other)
    return holders


def teammate_terms(
    state: GameState, view: OrgView, person_id: int, balance: Balance
) -> tuple[tuple[str, int, float], ...]:
    """(tag, holders, capped morale term) for every morale tag, in ORG_TAGS order."""
    holders = teammate_tag_holders(state, view, person_id)
    return tuple(
        (tag, len(holders[tag]), tag_term(tag, len(holders[tag]), balance.org)) for tag in ORG_TAGS
    )


def remote_morale(state: GameState, employment: Employment, balance: Balance) -> float:
    sociability = state.person(employment.person_id).personality[SOCIABILITY]
    return remote_term(sociability, is_remote(state, employment), balance.org)
