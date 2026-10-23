"""Hiring rules shared by actions, turn phases and previews (formulas.md section 7)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from tst.sim.data_models import Balance, GameData
from tst.sim.hiring.formulas import HintBand, hint_band, is_lowball, offer_score
from tst.sim.hiring.models import Candidate
from tst.sim.people.models import Person
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState


def matching_interests(person: Person, mission: tuple[str, ...]) -> int:
    return len(set(person.interests) & set(mission))


def equity_committed(state: GameState, company_id: int) -> int:
    """Equity held by staff plus pending offers, in basis points (the option pool)."""
    staff = sum(e.equity_bp for e in state.staff(company_id))
    pending = sum(o.equity_bp for o in state.pending_offers(company_id))
    return staff + pending


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
    committed = equity_committed(state, company_id) - replacing
    if committed + equity_bp > hiring.option_pool_bp:
        left = max(hiring.option_pool_bp - committed, 0)
        problems.append(
            f"the option pool has {left} bp left of {hiring.option_pool_bp} bp "
            "(staff plus pending offers)"
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
) -> OfferPreview:
    """The offer dialog's hint, from what the company knows (formulas.md section 7).

    R and equity are exact; F counts mission matches only once interests are revealed; risk
    appetite and ambition use the midpoints of their displayed ranges. Nothing is drawn or
    saved.
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
