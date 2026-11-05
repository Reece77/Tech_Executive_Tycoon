"""Recruitment fixes from playtest 2 (docs/formulas.md 29.5, M14b): Replace with a recruiter,
search by interest, and leadership fit from revealed values only."""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.people.models import Person, RevealState
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState

BP = 10_000  # tunable-exempt: basis points
RECRUITER_ROLE = "recruiter"
DEFAULT_LEVEL = "mid"
ATTR_MIN, ATTR_MAX = 1.0, 20.0  # tunable-exempt: the attribute scale
REPLACEABLE = ("resigned", "poached")


def interest_fee_cents(role: str, level: str | None, balance: Balance, data: GameData) -> int:
    """recruit.interest_fee_bp of the role's mid salary at the search's level (29.5)."""
    band = data.role(role).salary_band_mid_cents
    mid = band.get(level or DEFAULT_LEVEL, band[DEFAULT_LEVEL])
    return mid * balance.recruit.interest_fee_bp // BP


def recruiter_on_staff(state: GameState, company_id: int) -> int | None:
    """An active recruiter (the role), lowest person id first."""
    ids = [
        e.person_id
        for e in state.staff(company_id)
        if e.role == RECRUITER_ROLE and e.status == "active"
    ]
    return min(ids) if ids else None


def replace_problem(
    state: GameState, company_id: int, person_id: int, balance: Balance
) -> str | None:
    """Why Replace is not offered for this leaver, or None (29.5)."""
    e = state.employment_of(person_id)
    if e is None or e.company_id != company_id:
        e = next(
            (
                x
                for x in sorted(state.employments, key=lambda x: -x.id)
                if x.person_id == person_id and x.company_id == company_id
            ),
            None,
        )
    if e is None:
        return f"person {person_id} never worked here"
    resigning = e.status == "notice" and e.end_reason in REPLACEABLE
    left = (
        e.status == "ended"
        and e.end_reason in REPLACEABLE
        and e.end_turn is not None
        and state.turn - e.end_turn <= balance.recruit.replace_window
    )
    if not (resigning or left):
        return "Replace is for someone who resigned or was poached lately"
    if recruiter_on_staff(state, company_id) is None:
        return "Replace needs a recruiter on staff"
    if any(p.replace_of == person_id and p.status != "closed" for p in state.plans):
        return "a replacement is already being found"
    return None


def leaver_employment(state: GameState, company_id: int, person_id: int):  # type: ignore[no-untyped-def]
    return next(
        (
            x
            for x in sorted(state.employments, key=lambda x: -x.id)
            if x.person_id == person_id and x.company_id == company_id
        ),
        None,
    )


def skip_months(balance: Balance) -> int:
    """Months Replace saves: round(normal_months x (1 - replace_speed)) (29.5)."""
    rb = balance.recruit
    return round(rb.normal_months * (1 - rb.replace_speed))


def _stars(value: float, balance: Balance) -> float:
    lo, hi = balance.recruit.fit_stars
    return lo + (hi - lo) * (value - ATTR_MIN) / (ATTR_MAX - ATTR_MIN)


def leadership_fit(person: Person, reveal: RevealState | None, balance: Balance) -> tuple[int, int]:
    """A star range from the observer's revealed ranges of leadership, mentoring,
    communication and temperament (29.5): never the true values. With nothing revealed the
    range is the whole scale."""
    lo_stars, hi_stars = balance.recruit.fit_stars
    if reveal is None:
        return lo_stars, hi_stars
    lo = hi = 0.0
    for key, w in balance.recruit.fit_weights.items():
        a, b = revealed_range(person, reveal, key)
        lo += w * a
        hi += w * b
    low = max(lo_stars, min(hi_stars, int(_stars(lo, balance) + 0.5)))  # tunable-exempt: round
    high = max(low, min(hi_stars, int(_stars(hi, balance) + 0.5)))  # tunable-exempt: round
    return low, high
