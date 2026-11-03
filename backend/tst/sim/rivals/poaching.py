"""Poaching both ways (docs/formulas.md 15.6).

Rivals approach the player's people: an approach made in phase 2 is answered in phase 1 of
the next turn (stream `poach`, key `(approach_id,)`); an accepted offer is a resignation with
one month's notice, after which the person joins the rival as a key person.

The player poaches from rivals: a "Poach from a rival" search shows 2 to 4 of one rival's key
people as candidates who ask 1.3x their salary; the offer score loses 0.5 for leaving an
employer; a hire removes them from the rival, and a builder's leaving costs each of the
rival's products in their category 2 quality over the next 6 months (15.2).
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from tst.sim.data_models import Balance, GameData
from tst.sim.finance.captable import share_price
from tst.sim.hiring.models import Candidate, Search
from tst.sim.log import LogItem, inbox_item
from tst.sim.people.models import Employment
from tst.sim.rivals import formulas as f
from tst.sim.rivals.models import PoachApproach, RivalEffect, stream_key
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    with_approach,
    with_candidate,
    with_employment,
    with_person,
    with_rival_effect,
)

POACH_CHANNEL = "poach"


TARGET_KEY = 1  # tunable-exempt: tag of the target draw (M10d), apart from the answer's
ANSWER_KEY = 0  # tunable-exempt: tag of the employee's answer


def poach_draw(rng: RngFactory, turn: int, *key: int) -> float:
    """The `poach` stream's one call site (ADR-0013, amended in M12a): keyed by the rival's
    stable identity, never an approach id that more rivals would shift. Whom a new approach
    targets: (*rival key, TARGET_KEY), at most one approach a rival a month; an employee's
    answer: (*rival key, ANSWER_KEY, month the approach was made)."""
    return float(rng.stream(turn, "poach", *key).random())


def answer_key(state: GameState, approach: PoachApproach) -> tuple[int, ...]:
    rival = state.company(approach.rival_id)
    return (*stream_key(rival.id, rival.rival_key), ANSWER_KEY, approach.made_turn)


def unvested_ratio(state: GameState, person_id: int) -> float:
    """u = unvested option value / annual salary at today's share price (14.2)."""
    employment = state.employment_of(person_id)
    if employment is None or not employment.salary_cents:
        return 0.0
    grant = state.grant_for(employment.id)
    price = share_price(state, employment.company_id)
    if grant is None or price is None:
        return 0.0
    return float(grant.unvested * price) / employment.salary_cents


def approach_probability(
    state: GameState,
    approach: PoachApproach,
    balance: Balance,
    *,
    known_loyalty: float | None = None,
) -> float:
    """p for an approach at today's salary, morale, loyalty and options (15.6). The screens
    pass the displayed loyalty midpoint as `known_loyalty` and show only the band."""
    pb = balance.rivals.poach
    employment = state.employment_of(approach.person_id)
    person = state.person(approach.person_id)
    if employment is None or not employment.salary_cents:
        return 0.0
    morale = state.person_state(person.id).morale
    loyalty = person.personality["loyalty"] if known_loyalty is None else known_loyalty
    score = f.poach_score(
        approach.offer_cents / employment.salary_cents,
        balance.morale.new_hire if morale is None else morale,
        loyalty,
        unvested_ratio(state, person.id),
        pb,
    )
    return f.poach_probability(score, pb)


def answer_approaches(
    state: GameState, rng: RngFactory, balance: Balance
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Phase 1: each approach made before this turn is answered, by approach id."""
    logs: list[LogItem] = []
    for approach in sorted(state.approaches, key=lambda a: a.id):
        if approach.status != "pending" or approach.made_turn >= state.turn:
            continue
        employment = state.employment_of(approach.person_id)
        person = state.person(approach.person_id)
        rival = state.company(approach.rival_id)
        name = f"{person.first_name} {person.last_name}"
        if (
            employment is None
            or employment.company_id != state.player.id
            or employment.status != "active"
            or rival.failed_turn is not None
        ):
            state = with_approach(
                state, replace(approach, status="lapsed", resolved_turn=state.turn)
            )
            continue
        p = approach_probability(state, approach, balance)
        draw = poach_draw(rng, state.turn, *answer_key(state, approach))
        accepted = draw < p
        state = with_approach(
            state,
            replace(
                approach, status="accepted" if accepted else "declined", resolved_turn=state.turn
            ),
        )
        if accepted:
            state = with_employment(
                state,
                replace(employment, status="notice", end_turn=state.turn + 1, end_reason="poached"),
            )
        logs.append(
            inbox_item(
                state.turn,
                state.player.id,
                "poach_accepted" if accepted else "poach_declined",
                link_kind="person",
                link_id=person.id,
                name=name,
                rival=rival.name,
            )
        )
    return state, tuple(logs)


def join_rivals(state: GameState) -> GameState:
    """Phase 1, after notices end: people who accepted an approach join the rival as key
    people at the offered salary (15.6)."""
    for approach in state.approaches:
        if approach.status != "accepted":
            continue
        old = state.employment_of(approach.person_id)
        if old is not None:
            continue  # still serving notice (or rehired)
        ended = [
            e
            for e in state.employments
            if e.person_id == approach.person_id and e.end_reason == "poached"
        ]
        if not ended:
            continue
        last = max(ended, key=lambda e: e.id)
        emp_id, ids = state.next_ids.take("rival_employment")
        state = with_employment(
            replace(state, next_ids=ids),
            Employment(
                id=emp_id,
                person_id=approach.person_id,
                company_id=approach.rival_id,
                role=last.role,
                level=last.level,
                salary_cents=approach.offer_cents,
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
            ),
        )
        state = with_approach(state, replace(approach, status="joined"))
    return state


# --- The player's poach channel -----------------------------------------------------------------


def poach_batch(
    state: GameState,
    search: Search,
    gen: np.random.Generator,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, int]:
    """2 to 4 of the rival's key people in the search's role (any role if none), as
    candidates asking 1.3x their salary (15.6)."""
    pb = balance.rivals.poach
    count = int(gen.integers(int(pb.candidates.lo), int(pb.candidates.hi), endpoint=True))
    rival = search.rival_id
    if rival is None or state.company(rival).failed_turn is not None:
        return state, 0
    staff = sorted(
        (e for e in state.staff(rival) if e.status == "active"), key=lambda e: e.person_id
    )
    pool = [e for e in staff if e.role == search.role] or staff
    taken = {c.person_id for c in state.candidates if c.status == "open"}
    pool = [e for e in pool if e.person_id not in taken]
    picks = (
        [
            pool[int(i)]
            for i in sorted(gen.choice(len(pool), size=min(count, len(pool)), replace=False))
        ]
        if pool
        else []
    )
    for e in picks:
        person = state.person(e.person_id)
        ask = round(e.salary_cents * pb.ask_mult)
        state = with_person(state, replace(person, salary_expectation_cents=ask))
        state = with_candidate(
            state,
            Candidate(
                person_id=person.id,
                company_id=search.company_id,
                search_id=search.id,
                channel=POACH_CHANNEL,  # type: ignore[arg-type]
                created_turn=state.turn,
                expires_turn=state.turn + balance.hiring.candidate_shelf_turns,
            ),
        )
    return state, len(picks)


def leave_rival(state: GameState, person_id: int, balance: Balance, data: GameData) -> GameState:
    """A poached key person leaves their rival; a builder's leaving costs quality (15.6)."""
    employment = next(
        (
            e
            for e in state.employments
            if e.person_id == person_id
            and e.counts_as_staff
            and not state.company(e.company_id).is_player
        ),
        None,
    )
    if employment is None:
        return state
    state = with_employment(
        state, replace(employment, status="ended", end_turn=state.turn, end_reason="poached")
    )
    role = data.role(employment.role)
    if role.product_function != "builder":
        return state
    for product in state.company_products(employment.company_id):
        if product.status == "retired":
            continue
        effect_id, ids = state.next_ids.take("rival_effect")
        state = with_rival_effect(
            replace(state, next_ids=ids),
            RivalEffect(
                id=effect_id,
                company_id=employment.company_id,
                kind="builder_left",
                start_turn=state.turn,
                end_turn=state.turn + balance.rivals.push_turns - 1,
                product_id=product.id,
            ),
        )
    return state
