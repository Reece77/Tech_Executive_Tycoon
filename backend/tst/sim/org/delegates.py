"""Delegated hiring in phase 2 (docs/formulas.md 13.10, ADR-0015).

For each active plan in id order, its delegate opens a search if the plan is short and none
is open for the role, interviews the best candidates the company does not know well, scouts
with leftover energy, and makes offers. Every choice is an ordinary `Action` applied through
`apply_action` with the delegate as actor, so energy, rules and the offer pitch all apply.
Choosing is deterministic; randomness happens only inside the actions, from stream
`delegate` keyed (person_id, n), where n counts that delegate's actions this turn.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from fractions import Fraction

import numpy as np

from tst.sim.actions import (
    Action,
    CloseSearch,
    Interview,
    MakeOffer,
    OpenSearch,
    Scout,
    apply_action,
)
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import SimError
from tst.sim.hiring.formulas import energy_cost
from tst.sim.hiring.models import Candidate, Channel
from tst.sim.ledger import AccountCode, LedgerEntry, apply_entries
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import BP_DENOMINATOR, Cents
from tst.sim.org.models import POTENTIAL_LEVELS, HiringPlan, PlanActivity, PlanFocus
from tst.sim.org.upkeep import release_job_posts
from tst.sim.people.models import PA_KEY
from tst.sim.people.reveal import revealed_range
from tst.sim.rng import RngFactory
from tst.sim.scale import PRIMARY_WEIGHT, SECONDARY_WEIGHT
from tst.sim.state import GameState, with_person_state, with_plan

ANY_CHANNEL: Channel = "job_post"  # a plan on channel "any" searches with a job post (13.10)

type DelegateAction = tuple[int, Action]  # (company id, action), in the order taken


def known_score(state: GameState, company_id: int, candidate: Candidate, data: GameData) -> float:
    """The company's displayed range midpoints of the role's skills, primary x 3 (13.10)."""
    person = state.person(candidate.person_id)
    reveal = state.reveal(company_id, person.id)
    if reveal is None or person.role is None:
        return 0.0
    role = data.role(person.role)

    def mid(skill: str) -> float:
        lo, hi = revealed_range(person, reveal, skill)
        return (lo + hi) / 2

    return PRIMARY_WEIGHT * sum(mid(s) for s in role.primary) + SECONDARY_WEIGHT * sum(
        mid(s) for s in role.secondary
    )


def known_potential(state: GameState, company_id: int, candidate: Candidate) -> float:
    """Midpoint of the company's displayed PA range (13.10 focus potential)."""
    reveal = state.reveal(company_id, candidate.person_id)
    if reveal is None:
        return 0.0
    lo, hi = revealed_range(state.person(candidate.person_id), reveal, PA_KEY)
    return (lo + hi) / 2


def ranked_candidates(
    state: GameState, company_id: int, role: str, data: GameData, focus: PlanFocus = "current"
) -> list[Candidate]:
    """The role's open candidates, best first (13.10, step 2).

    Focus current: by the known role-skill score, ties by candidate id. Focus potential:
    juniors and mids only, by the known PA midpoint, ties by the role-skill score, then id.
    """
    pool = [c for c in state.open_candidates(company_id) if state.person(c.person_id).role == role]
    if focus == "potential":
        pool = [c for c in pool if state.person(c.person_id).level in POTENTIAL_LEVELS]
        return sorted(
            pool,
            key=lambda c: (
                -known_potential(state, company_id, c),
                -known_score(state, company_id, c, data),
                c.person_id,
            ),
        )
    return sorted(pool, key=lambda c: (-known_score(state, company_id, c, data), c.person_id))


def plan_offer_salary(ask_cents: Cents, ratio_bp: int) -> Cents:
    """The ask x the plan's ratio, rounded half to even to whole cents."""
    return round(Fraction(ask_cents * ratio_bp, BP_DENOMINATOR))


def still_needed(state: GameState, plan: HiringPlan) -> int:
    pending = sum(1 for o in state.pending_offers(plan.company_id) if o.plan_id == plan.id)
    return plan.target - plan.hired - pending


@dataclass(slots=True)
class _Run:
    """Accumulates one phase 2: the state, running balances, and everything to report."""

    state: GameState
    balances: dict[tuple[int, AccountCode], Cents]
    rng: RngFactory
    balance: Balance
    data: GameData
    entries: list[LedgerEntry] = field(default_factory=list)
    logs: list[LogItem] = field(default_factory=list)
    taken: list[DelegateAction] = field(default_factory=list)
    counts: dict[int, int] = field(default_factory=dict)  # actions per delegate this turn

    def energy(self, person_id: int) -> int:
        return self.state.person_state(person_id).energy or 0

    def attempt(self, company_id: int, action: Action) -> bool:
        """Apply the action if the rules allow it; a refused action changes nothing."""
        actor = action.actor_id
        n = self.counts.get(actor, 0)
        turn = self.state.turn

        def draws() -> np.random.Generator:
            return self.rng.stream(turn, "delegate", actor, n)

        try:
            out = apply_action(
                self.state,
                action,
                self.rng,
                self.balance,
                self.data,
                self.balances,
                seq=0,
                draws=draws,
            )
        except SimError:
            return False
        self.state = out.new_state
        self.balances = apply_entries(self.balances, out.ledger_entries)
        self.entries += out.ledger_entries
        self.logs += out.log_items
        self.taken.append((company_id, action))
        self.counts[actor] = n + 1
        return True


def _work_plan(run: _Run, plan: HiringPlan) -> PlanActivity:
    """Steps 1-5 of formulas.md 13.10 for one plan."""
    company, owner, role = plan.company_id, plan.owner_id, plan.role
    activity = PlanActivity(turn=run.state.turn)
    reserve = run.balance.delegates.scout_cost
    interview_cost = energy_cost("interview", run.balance)

    # 1. Short, and nothing open for the role: open a search.
    searching = any(s.role == role for s in run.state.open_searches(company))
    if still_needed(run.state, plan) > 0 and not searching:
        channel: Channel = ANY_CHANNEL if plan.channel == "any" else plan.channel
        if run.attempt(company, OpenSearch(owner, role, channel, plan_id=plan.id)):
            activity = replace(activity, searches=activity.searches + 1)

    # 2-3. Interview the best uninterviewed candidates while more than the reserve would remain.
    for candidate in ranked_candidates(run.state, company, role, run.data, plan.focus):
        if candidate.interviewed_turn is not None:
            continue
        if run.energy(owner) - interview_cost <= reserve:
            break
        if run.attempt(company, Interview(owner, candidate.person_id)):
            activity = replace(activity, interviews=activity.interviews + 1)

    # 4. Scout every open candidate for the role with the energy left.
    pool = ranked_candidates(run.state, company, role, run.data)
    if pool and run.energy(owner) >= reserve and run.attempt(company, Scout(owner, role)):
        activity = replace(activity, scouted=activity.scouted + len(pool))

    # 5. Offer to the best interviewed candidates without a pending offer, as many as needed.
    needed = still_needed(run.state, plan)
    for candidate in ranked_candidates(run.state, company, role, run.data, plan.focus):
        if needed <= 0:
            break
        if candidate.interviewed_turn is None:
            continue
        if run.state.pending_offer_for(candidate.person_id) is not None:
            continue
        ask = run.state.person(candidate.person_id).salary_expectation_cents or 0
        offer = MakeOffer(
            owner,
            candidate.person_id,
            plan_offer_salary(ask, plan.ratio_bp),
            plan.equity_bp,
            plan_id=plan.id,
        )
        if run.attempt(company, offer):
            needed -= 1
            activity = replace(activity, offers=activity.offers + 1)
    return activity


def _plural(word: str, count: int) -> str:
    return word if count == 1 else f"{word}s"


def activity_text(activity: PlanActivity, role_label: str, focus: PlanFocus = "current") -> str:
    """'interviewed 4 software engineers and made 2 offers', plus ', favouring potential'
    for a potential plan (13.10)."""
    parts = []
    if activity.searches:
        parts.append("opened a new search")
    if activity.interviews:
        parts.append(
            f"interviewed {activity.interviews} {_plural(role_label, activity.interviews)}"
        )
    if activity.scouted:
        parts.append(f"scouted {activity.scouted} {_plural('candidate', activity.scouted)}")
    if activity.offers:
        parts.append(f"made {activity.offers} {_plural('offer', activity.offers)}")
    text = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    return f"{text}, favouring potential" if focus == "potential" else text


def run_delegates(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...], tuple[DelegateAction, ...]]:
    """Phase 2 for every company's delegates (ADR-0015). Plans act in id order."""
    run = _Run(state=state, balances=dict(balances), rng=rng, balance=balance, data=data)
    # Filled plans give up their job posts first (13.10): the delegate closes them.
    for plan_id in sorted(p.id for p in state.plans):
        plan = run.state.plan(plan_id)
        if plan is None or plan.status != "filled":
            continue
        run.state, to_close = release_job_posts(run.state, plan)
        for search in to_close:
            run.attempt(plan.company_id, CloseSearch(plan.owner_id, search.id))
    for plan_id in sorted(p.id for p in state.plans):
        plan = run.state.plan(plan_id)
        if plan is None or plan.status != "active":
            continue
        employment = run.state.employment_of(plan.owner_id)
        if employment is None or employment.company_id != plan.company_id:
            continue  # detach_departed pauses it in phase 1
        ps = run.state.person_state(plan.owner_id)
        if ps.energy is None:
            run.state = with_person_state(
                run.state, replace(ps, energy=balance.delegates.energy_per_month)
            )
        activity = _work_plan(run, plan)
        if not activity.acted:
            continue
        current = run.state.plan(plan_id)
        assert current is not None
        run.state = with_plan(run.state, replace(current, last_activity=activity))
        owner = run.state.person(plan.owner_id)
        role_label = data.role(plan.role).label.lower()
        run.logs.append(
            inbox_item(
                run.state.turn,
                plan.company_id,
                "plan_activity",
                link_kind="person",
                link_id=owner.id,
                name=f"{owner.first_name} {owner.last_name}",
                role=role_label,
                activity=activity_text(activity, role_label, plan.focus),
            )
        )
    return run.state, tuple(run.entries), tuple(run.logs), tuple(run.taken)
