"""Hiring actions (ADR-0014): they take effect at once, in their own transaction.

Every action names an `actor_id`: the founder, or a delegate running a hiring plan (M2,
ADR-0015), through the same functions. The actor's employer is the acting company. Energy is
spent at once by whoever tracks it (the founder and delegates); anyone else spends none.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import (
    InsufficientCashError,
    InsufficientEnergyError,
    InterviewRequired,
    InvalidActionError,
    OfferExistsError,
    OptionPoolError,
    UnknownCandidateError,
    UnknownOfferError,
    UnknownPersonError,
    UnknownPlanError,
    UnknownRoleError,
    UnknownSearchError,
)
from tst.sim.finance.board import vacate_departed
from tst.sim.finance.options import settle_leavers
from tst.sim.hiring.formulas import ROLL_RANGE, energy_cost, roll_succeeds, severance_cents
from tst.sim.hiring.models import Candidate, Channel, Offer, Search
from tst.sim.hiring.rules import offer_problems
from tst.sim.ledger import (
    CASH,
    SALARIES,
    LedgerBalances,
    LedgerEntry,
    LedgerLine,
    account_balance,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.org.divisions import division_of_unit
from tst.sim.org.executives import seats_in_play
from tst.sim.org.upkeep import detach_departed
from tst.sim.people.models import Person
from tst.sim.people.reveal import apply_knowledge_action
from tst.sim.scale import clamp_morale
from tst.sim.state import (
    GameState,
    with_candidate,
    with_employment,
    with_offer,
    with_person_state,
    with_reveal,
    with_search,
)

CULTURE_CARRIER = "culture_carrier"
EXEC_SEARCH_LEVEL = "exec"  # tunable-exempt: the one level a search may target (18.3)
CHANNEL_ENERGY: dict[str, str] = {
    "network": "network",
    "job_post": "job_post",
    "recruiter": "recruiter",
    "poach": "poach_search",  # M5 (15.6)
}


# --- Action types ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OpenSearch:
    actor_id: int
    role: str
    channel: Channel
    plan_id: int | None = None  # set by a delegate opening it for a hiring plan (13.10)
    rival_id: int | None = None  # the rival of a "Poach from a rival" search (M5, 15.6)
    level: str | None = None  # "exec": an exec-level search, from stage 3 (M8, 18.3)
    # M9 (19.3): the city candidates live in, or "anywhere" for a remote unit; None: the
    # hiring unit's office city. `unit_id` names the hiring unit (None: the plan's unit, or
    # the company root).
    city: str | None = None
    unit_id: int | None = None
    kind: Literal["open_search"] = "open_search"


@dataclass(frozen=True, slots=True)
class CloseSearch:
    actor_id: int
    search_id: int
    kind: Literal["close_search"] = "close_search"


@dataclass(frozen=True, slots=True)
class Interview:
    actor_id: int
    candidate_id: int
    kind: Literal["interview"] = "interview"


@dataclass(frozen=True, slots=True)
class ReferenceCheck:
    actor_id: int
    candidate_id: int
    kind: Literal["reference_check"] = "reference_check"


@dataclass(frozen=True, slots=True)
class MakeOffer:
    actor_id: int
    candidate_id: int
    salary_cents: int
    equity_bp: int
    plan_id: int | None = None  # set by a delegate working a hiring plan (ADR-0015)
    kind: Literal["make_offer"] = "make_offer"


@dataclass(frozen=True, slots=True)
class WithdrawOffer:
    actor_id: int
    offer_id: int
    kind: Literal["withdraw_offer"] = "withdraw_offer"


@dataclass(frozen=True, slots=True)
class Fire:
    actor_id: int
    person_id: int
    kind: Literal["fire"] = "fire"


type HiringAction = (
    OpenSearch | CloseSearch | Interview | ReferenceCheck | MakeOffer | WithdrawOffer | Fire
)
# The generator for randomness inside one action, created only if the action draws: stream
# `actions` keyed by seq for the player, `delegate` keyed (person, n) for delegates (ADR-0015).
type Draws = Callable[[], np.random.Generator]


@dataclass(frozen=True, slots=True)
class Outcome:
    state: GameState
    entries: tuple[LedgerEntry, ...] = ()
    log: tuple[LogItem, ...] = ()


# --- Shared steps ---------------------------------------------------------------------------


def acting_company(state: GameState, actor_id: int) -> int:
    employment = state.employment_of(actor_id)
    if employment is None:
        raise UnknownPersonError(f"person {actor_id} is not on staff and cannot act")
    return employment.company_id


def spend_energy(
    state: GameState, actor_id: int, action: str, balance: Balance, *, cost: int | None = None
) -> GameState:
    """Spend `cost` (default: founder.energy_cost[action]) from the actor's energy."""
    if cost is None:
        cost = energy_cost(action, balance)
    ps = state.person_state(actor_id)
    if ps.energy is None:
        return state  # this person does not track energy
    if ps.energy < cost:
        raise InsufficientEnergyError(f"{action} needs {cost} energy; {ps.energy} left this month")
    return with_person_state(state, replace(ps, energy=ps.energy - cost))


def open_candidate(state: GameState, company_id: int, candidate_id: int) -> Candidate:
    candidate = state.candidate(candidate_id)
    if candidate is None or candidate.company_id != company_id or candidate.status != "open":
        raise UnknownCandidateError(f"no open candidate {candidate_id}")
    return candidate


def judgment(person: Person) -> float:
    return person.skills["judgment_of_talent"]


# --- Actions --------------------------------------------------------------------------------


def open_search(
    state: GameState,
    action: OpenSearch,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    if action.role not in {r.key for r in data.roles}:
        raise UnknownRoleError(f"unknown role {action.role!r}")
    if action.channel not in CHANNEL_ENERGY:
        raise InvalidActionError(f"unknown channel {action.channel!r}")
    if action.channel == "job_post":
        fee = balance.hiring.job_post_cost_cents
        cash = account_balance(balances, company, CASH)
        if cash < fee:
            raise InsufficientCashError(
                f"a job post needs at least its first month's fee in cash ({fee} cents)"
            )
    if action.plan_id is not None:
        plan = state.plan(action.plan_id)
        if plan is None or plan.company_id != company or plan.status == "closed":
            raise UnknownPlanError(f"no hiring plan {action.plan_id}")
    if action.channel == "poach":
        rival = next((c for c in state.rivals() if c.id == action.rival_id), None)
        if rival is None or rival.id == company:
            raise InvalidActionError("a poach search needs a rival still in business")
    elif action.rival_id is not None:
        raise InvalidActionError("only a poach search names a rival")
    if action.level is not None:  # M8 (18.3)
        if action.level != EXEC_SEARCH_LEVEL or action.channel == "poach":
            raise InvalidActionError("a search may target only exec level, and not a poach")
        if not seats_in_play(state, company, balance):
            raise InvalidActionError(f"exec searches open at stage {balance.exec_seats.stage}")
    city = search_city(state, company, action, balance, data)
    state = spend_energy(state, action.actor_id, CHANNEL_ENERGY[action.channel], balance)
    search_id, ids = state.next_ids.take("search")
    search = Search(
        id=search_id,
        company_id=company,
        role=action.role,
        channel=action.channel,
        actor_id=action.actor_id,
        opened_turn=state.turn,
        plan_id=action.plan_id,
        rival_id=action.rival_id,
        level=action.level,
        city=city,
    )
    return Outcome(replace(with_search(state, search), next_ids=ids))


def search_city(
    state: GameState, company: int, action: OpenSearch, balance: Balance, data: GameData
) -> str | None:
    """The search's city (19.3): the one asked for, else the hiring unit's office city.
    "Anywhere" only for a remote unit. None for a poach search or without cities.yaml."""
    from tst.sim.geo.cities import office_city
    from tst.sim.geo.models import ANYWHERE
    from tst.sim.org.rules import effective_policy

    if action.channel == "poach" or not data.cities:
        if action.city is not None and action.channel == "poach":
            raise InvalidActionError("a poach search has no city")
        return None
    unit_id = action.unit_id
    if unit_id is None and action.plan_id is not None:
        plan = state.plan(action.plan_id)
        unit_id = plan.unit_id if plan is not None else None
    if unit_id is not None:
        unit = state.unit(unit_id)
        if unit is None or unit.company_id != company or unit.status != "active":
            raise InvalidActionError(f"no unit {unit_id}")
    if action.city == ANYWHERE:
        if effective_policy(state, company, unit_id) != "remote":
            raise InvalidActionError("only a search for a remote unit can look anywhere")
        return ANYWHERE
    if action.city is not None:
        if not data.has_city(action.city):
            raise InvalidActionError(f"unknown city {action.city!r}")
        return action.city
    return office_city(state, company, unit_id, balance)


def close_search(state: GameState, action: CloseSearch) -> Outcome:
    company = acting_company(state, action.actor_id)
    search = state.search(action.search_id)
    if search is None or search.company_id != company or search.status != "open":
        raise UnknownSearchError(f"no open search {action.search_id}")
    closed = replace(search, status="closed", closed_turn=state.turn)
    return Outcome(with_search(state, closed))


def _check_tags(
    state: GameState,
    company: int,
    person: Person,
    draws: Draws,
    balance: Balance,
) -> GameState:
    """One roll per still-hidden tag, in the person's tag order, at reveal_bp_on_check
    (the action's generator: stream actions keyed by seq, or delegate keyed (person, n))."""
    reveal = state.reveal(company, person.id)
    if reveal is None:
        return state
    known = {tag for tag, _ in reveal.revealed_tags}
    gen = draws()
    found = []
    for tag in person.tags:
        if tag in known:
            continue
        if roll_succeeds(int(gen.integers(0, ROLL_RANGE)), balance.tags.reveal_bp_on_check):
            found.append(tag)
    if not found:
        return state
    reveal = replace(
        reveal, revealed_tags=reveal.revealed_tags + tuple((t, state.turn) for t in found)
    )
    return with_reveal(state, reveal)


def check_candidate(
    state: GameState,
    actor_id: int,
    candidate_id: int,
    action: Literal["interview", "reference_check"],
    draws: Draws,
    balance: Balance,
    data: GameData,
) -> Outcome:
    company = acting_company(state, actor_id)
    candidate = open_candidate(state, company, candidate_id)
    state = spend_energy(state, actor_id, action, balance)
    person = state.person(candidate.person_id)
    reveal = state.reveal(company, person.id)
    if reveal is None:
        raise UnknownCandidateError(f"no knowledge record for candidate {candidate_id}")
    reveal = apply_knowledge_action(
        reveal,
        action,
        judgment(state.person(actor_id)),
        balance,
        turn=state.turn,
        skill_keys=frozenset(data.skill_keys),
    )
    state = with_reveal(state, reveal)
    before = {t for t, _ in reveal.revealed_tags}
    if action == "interview" and candidate.interviewed_turn is None:
        state = with_candidate(state, replace(candidate, interviewed_turn=state.turn))
    state = _check_tags(state, company, person, draws, balance)
    after = state.reveal(company, person.id)
    assert after is not None
    log = tuple(
        inbox_item(
            state.turn,
            company,
            "tag_revealed",
            link_kind="candidate",
            link_id=person.id,
            name=f"{person.first_name} {person.last_name}",
            reveal_text=_reveal_text(tag, data),
        )
        for tag, _ in after.revealed_tags
        if tag not in before
    )
    return Outcome(state, log=log)


def _reveal_text(tag: str, data: GameData) -> str:
    return next(t.reveal_text for t in data.tags if t.key == tag)


def make_offer(state: GameState, action: MakeOffer, balance: Balance) -> Outcome:
    company = acting_company(state, action.actor_id)
    candidate = open_candidate(state, company, action.candidate_id)
    if candidate.interviewed_turn is None:
        raise InterviewRequired(
            f"interview candidate {candidate.person_id} before making an offer (ADR-0016)"
        )
    if state.pending_offer_for(candidate.person_id) is not None:
        raise OfferExistsError(
            f"candidate {candidate.person_id} already has a pending offer; withdraw it first"
        )
    if action.salary_cents <= 0:
        raise InvalidActionError("salary must be positive")
    problems = offer_problems(state, company, action.equity_bp, balance)
    if problems:
        raise OptionPoolError("; ".join(problems))
    unit_id = None
    if action.plan_id is not None:
        plan = state.plan(action.plan_id)
        if plan is None or plan.company_id != company or plan.status == "closed":
            raise UnknownPlanError(f"no hiring plan {action.plan_id}")
        unit_id = plan.unit_id
    state = spend_energy(state, action.actor_id, "offer", balance)
    offer_id, ids = state.next_ids.take("offer")
    offer = Offer(
        id=offer_id,
        company_id=company,
        candidate_id=candidate.person_id,
        actor_id=action.actor_id,
        salary_cents=action.salary_cents,
        equity_bp=action.equity_bp,
        made_turn=state.turn,
        plan_id=action.plan_id,
        unit_id=unit_id,
    )
    return Outcome(replace(with_offer(state, offer), next_ids=ids))


def withdraw_offer(state: GameState, action: WithdrawOffer) -> Outcome:
    """Removes the pending offer; the candidate stays open (formulas.md section 7)."""
    company = acting_company(state, action.actor_id)
    offer = state.offer(action.offer_id)
    if offer is None or offer.company_id != company or offer.status != "pending":
        raise UnknownOfferError(f"no pending offer {action.offer_id}")
    return Outcome(with_offer(state, replace(offer, status="withdrawn", resolved_turn=state.turn)))


def fire(state: GameState, action: Fire, balance: Balance, data: GameData) -> Outcome:
    company = acting_company(state, action.actor_id)
    employment = state.employment_of(action.person_id)
    if employment is None or employment.company_id != company:
        raise UnknownPersonError(f"person {action.person_id} is not on staff")
    person = state.person(action.person_id)
    if person.is_founder:
        raise InvalidActionError("the founder cannot be fired")
    if person.id == action.actor_id:
        raise InvalidActionError("an actor cannot fire themselves")

    state = with_employment(
        state, replace(employment, status="ended", end_turn=state.turn, end_reason="fired")
    )
    state = settle_leavers(state)  # unvested options return to the pool (14.2)
    severance = severance_cents(employment.salary_cents, balance.payroll)
    entries: tuple[LedgerEntry, ...] = ()
    if severance:
        units = {u.id: u for u in state.active_units(company)}
        d = division_of_unit(units, employment.unit_id)  # their division (M8, 18.1)
        entries = (
            LedgerEntry(
                turn=state.turn,
                company_id=company,
                memo=f"Severance: {person.first_name} {person.last_name}",
                lines=(LedgerLine(SALARIES, severance, d), LedgerLine(CASH, -severance, d)),
            ),
        )
    penalty = (
        balance.morale.fire_penalty_culture_carrier
        if CULTURE_CARRIER in person.tags
        else balance.morale.fire_penalty
    )
    for other in state.staff(company):
        ps = state.person_state(other.person_id)
        if ps.morale is not None:
            state = with_person_state(state, replace(ps, morale=clamp_morale(ps.morale + penalty)))
    name = f"{person.first_name} {person.last_name}"
    log: tuple[LogItem, ...] = (
        inbox_item(state.turn, company, "fired", name=name, severance_cents=severance),
    )
    state, detached = detach_departed(state, data)
    log += detached
    state, vacated = vacate_departed(state)  # a nominee's board seat empties (14.6, M4c)
    log += vacated
    # The larger morale hit gives the tag away, so the company learns it now (M1c brief).
    reveal = state.reveal(company, person.id)
    if (
        CULTURE_CARRIER in person.tags
        and reveal is not None
        and CULTURE_CARRIER not in {t for t, _ in reveal.revealed_tags}
    ):
        state = with_reveal(
            state,
            replace(reveal, revealed_tags=(*reveal.revealed_tags, (CULTURE_CARRIER, state.turn))),
        )
        log += (
            inbox_item(
                state.turn,
                company,
                "culture_carrier_left",
                link_kind="person",
                link_id=person.id,
                name=name,
            ),
        )
    return Outcome(state, entries, log)
