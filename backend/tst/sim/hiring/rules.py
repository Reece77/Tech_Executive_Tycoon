"""Hiring rules shared by actions, turn phases and previews (formulas.md section 7)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from tst.sim.data_models import Balance, GameData, HiringBalance
from tst.sim.finance.captable import unallocated
from tst.sim.finance.options import offer_shares, pending_offer_shares
from tst.sim.hiring.formulas import HintBand, hint_band, is_lowball, offer_score
from tst.sim.hiring.models import Candidate
from tst.sim.org.formulas import pitch
from tst.sim.people.models import Person
from tst.sim.people.reveal import revealed_range
from tst.sim.press.moments import hiring_appeal
from tst.sim.state import GameState

RECRUITING = "recruiting"


def offer_pitch(state: GameState, actor_id: int, hiring: HiringBalance) -> float:
    """The pitch term from the true recruiting skill of whoever made the offer (7, M2)."""
    return pitch(state.person(actor_id).skills[RECRUITING], hiring)


def matching_interests(person: Person, mission: tuple[str, ...]) -> int:
    return len(set(person.interests) & set(mission))


def offer_problems(
    state: GameState, company_id: int, equity_bp: int, balance: Balance, *, replacing: int = 0
) -> tuple[str, ...]:
    """Rules an offer would break. `replacing` is equity of a pending offer it replaces."""
    hiring = balance.hiring
    problems = []
    if equity_bp < 0:
        problems.append("equity cannot be negative")
    if equity_bp > hiring.max_offer_equity_bp:
        problems.append(f"an offer may carry at most {hiring.max_offer_equity_bp} bp of equity")
    # M4 (14.2): pending offers plus this one may not exceed the unallocated pool.
    pool = unallocated(state, company_id)
    promised = pending_offer_shares(state, company_id, excluding=replacing)
    wanted = offer_shares(state, company_id, max(equity_bp, 0))
    if promised + wanted > pool:
        left = max(pool - promised, 0)
        problems.append(
            f"the option pool has {left:,} unallocated options left after pending offers; "
            f"this offer needs {wanted:,}"
        )
    return tuple(problems)


def floor_cents(expectation_cents: int, balance: Balance) -> int:
    """Lowest salary that is not an automatic decline: ceil(expectation x lowball_ratio)."""
    exact = Fraction(expectation_cents) * Fraction(str(balance.hiring.lowball_ratio))
    return math.ceil(exact)


@dataclass(frozen=True, slots=True)
class OfferPreview:
    hint: HintBand
    ratio: float  # offered salary / expectation
    floor_cents: int
    expectation_cents: int
    problems: tuple[str, ...]


def offer_preview(
    state: GameState,
    candidate: Candidate,
    salary_cents: int,
    equity_bp: int,
    balance: Balance,
    data: GameData,
    actor_id: int | None = None,
) -> OfferPreview:
    """The offer dialog's hint, from what the company knows (formulas.md section 7).

    R and equity are exact; F counts mission matches only once interests are revealed; risk
    appetite and ambition use the midpoints of their displayed ranges; the pitch comes from
    the offer maker (`actor_id`, usually the founder, whom the company knows exactly). Nothing
    is drawn or saved.
    """
    person = state.person(candidate.person_id)
    company = state.company(candidate.company_id)
    expectation = person.salary_expectation_cents or 0
    ratio = salary_cents / expectation if expectation else 0.0
    reveal = state.reveal(company.id, person.id)
    if reveal is None:  # every candidate gets a knowledge record when generated
        raise RuntimeError(f"company {company.id} has no knowledge of candidate {person.id}")
    fit = 0 if reveal.profile_revealed_turn is None else matching_interests(person, company.mission)

    def midpoint(trait: str) -> float:
        lo, hi = revealed_range(person, reveal, trait)
        return (lo + hi) / 2

    score = offer_score(
        ratio=ratio,
        equity_bp=equity_bp,
        matching_interests=fit,
        risk_appetite=midpoint("risk_appetite"),
        ambition=midpoint("ambition"),
        stage=company.stage,
        offer=balance.hiring.offer,
        pitch=(0.0 if actor_id is None else offer_pitch(state, actor_id, balance.hiring))
        + (balance.rivals.poach.leave_penalty if candidate.channel == "poach" else 0.0)
        + hiring_appeal(state, company.id, balance),  # M14b (29.3): credibility
    )
    pending = state.pending_offer_for(person.id)
    problems = offer_problems(
        state,
        company.id,
        equity_bp,
        balance,
        replacing=pending.equity_bp if pending else 0,
    )
    hint: HintBand = (
        "unlikely" if is_lowball(ratio, balance.hiring) else hint_band(score, balance.hiring)
    )
    return OfferPreview(
        hint=hint,
        ratio=ratio,
        floor_cents=floor_cents(expectation, balance),
        expectation_cents=expectation,
        problems=problems,
    )
