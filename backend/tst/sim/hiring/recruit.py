"""Recruitment fixes from playtest 2 (docs/formulas.md 29.5, M14b): Replace with a recruiter,
search by interest, and leadership fit from revealed values only."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.people.models import Person, RevealState
from tst.sim.people.reveal import revealed_range
from tst.sim.press.models import Departure
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


def leaver(state: GameState, company_id: int, person_id: int) -> Departure | None:
    """A resignation serving notice, or a departure of the last replace_window months."""
    e = state.employment_of(person_id)
    if (
        e is not None
        and e.company_id == company_id
        and e.status == "notice"
        and e.end_reason in REPLACEABLE
    ):
        return Departure(
            person_id, company_id, e.role, e.level, e.unit_id, e.end_reason or "", state.turn
        )
    return next(
        (d for d in state.departures if d.person_id == person_id and d.company_id == company_id),
        None,
    )


def replace_problem(
    state: GameState, company_id: int, person_id: int, balance: Balance
) -> str | None:
    """Why Replace is not offered for this leaver, or None (29.5)."""
    left = leaver(state, company_id, person_id)
    if left is None or state.turn - left.turn > balance.recruit.replace_window:
        return "Replace is for someone who resigned or was poached lately"
    if recruiter_on_staff(state, company_id) is None:
        return "Replace needs a recruiter on staff"
    if any(p.replace_of == person_id and p.status != "closed" for p in state.plans):
        return "a replacement is already being found"
    return None


def record_departures(state: GameState, balance: Balance) -> GameState:
    """Phase 12: the player's resignations and poaches that ended this month are kept for
    Replace; older ones drop."""
    players = {c.id for c in state.companies if c.is_player}
    new = [
        Departure(
            e.person_id, e.company_id, e.role, e.level, e.unit_id, e.end_reason or "", state.turn
        )
        for e in state.employments
        if e.company_id in players
        and e.status == "ended"
        and e.end_turn == state.turn
        and e.end_reason in REPLACEABLE
    ]
    keep = state.turn - balance.recruit.replace_window
    kept = {d.person_id: d for d in state.departures if d.turn >= keep}
    for d in new:
        kept[d.person_id] = d
    return replace(state, departures=tuple(kept[k] for k in sorted(kept)))


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
