"""Owners and eligibility (docs/formulas.md 40.1), area scores (40.3) and default limits
(40.2). True scores decide how well an owner decides and are never shown; the player sees
only fit bands from displayed ranges (18.8, 40.11)."""

from __future__ import annotations

from tst.sim.automation.config import SEAT_AREA
from tst.sim.automation.models import AreaOwner, OwnerKind
from tst.sim.data_models import LEVELS, AutomationArea, Balance, GameData
from tst.sim.markets_public.formulas import ceo_score
from tst.sim.money import BP_DENOMINATOR, Cents
from tst.sim.org.executives import displayed_score, true_score
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState, ceo_of

FIT_WORDS = ("weak fit", "fair fit", "strong fit")
NEUTRAL_SCORE = 10.0  # tunable-exempt: the attribute scale's middle, for an unknown person


def area_keys(balance: Balance) -> tuple[str, ...]:
    return tuple(balance.automation.areas)


def area_def(balance: Balance, area: str) -> AutomationArea:
    return balance.automation.areas[area]


def area_index(balance: Balance, area: str) -> int:
    """The area's fixed index: its draws' key in stream `automation` (40.3)."""
    return area_keys(balance).index(area)


def is_existing(area: str) -> bool:
    """An area whose monthly rule is a seat's existing rule (24.1, 27.1)."""
    return area in SEAT_AREA.values()


def _active(state: GameState, person_id: int, company_id: int) -> bool:
    e = state.employment_of(person_id)
    return e is not None and e.company_id == company_id and e.status == "active"


def owner_kind(
    state: GameState, company_id: int, area: str, person_id: int, b: Balance
) -> OwnerKind | None:
    """How this person may own the area, or None (40.1). The founder never may."""
    person = state.person(person_id)
    if person.is_founder or not _active(state, person_id, company_id):
        return None
    a = area_def(b, area)
    if a.seat is not None and state.seat_holder(company_id, a.seat) == person_id:
        return "seat"
    ceo = ceo_of(state, company_id)
    if ceo is not None and ceo.person_id == person_id:
        return "subsidiary_ceo" if company_id != state.player.id else "ceo"
    e = state.employment_of(person_id)
    min_level = LEVELS.index(b.automation.lead_min_level)
    if (
        e is not None
        and e.role in a.roles
        and e.level in LEVELS
        and LEVELS.index(e.level) >= min_level
    ):
        return "lead"
    return None


def eligible_people(
    state: GameState, company_id: int, area: str, b: Balance
) -> list[tuple[int, OwnerKind]]:
    """Everyone who may own the area: seat holders first, then the CEO, then leads by id."""
    out: list[tuple[int, OwnerKind]] = []
    for e in state.staff(company_id):
        kind = owner_kind(state, company_id, area, e.person_id, b)
        if kind is not None:
            out.append((e.person_id, kind))
    order = {"seat": 0, "ceo": 1, "subsidiary_ceo": 1, "lead": 2}
    out.sort(key=lambda t: (order[t[1]], t[0]))
    return out


def cant_automate(
    state: GameState, company_id: int, area: str, b: Balance, data: GameData
) -> str | None:
    """Why nobody can own the area yet, with how to fix it (40.8), or None."""
    if eligible_people(state, company_id, area, b):
        return None
    a = area_def(b, area)
    level = b.automation.lead_min_level
    roles = [data.role(r).label.lower() for r in a.roles]
    fixes = []
    if roles:
        fixes.append(f"hire a {level} {' or '.join(roles)}")
    if a.seat is not None:
        fixes.append(f"fill the {a.seat.upper()} seat")
    return " or ".join(fixes) if fixes else "appoint a CEO"


def true_area_score(
    state: GameState, company_id: int, area: str, person_id: int, b: Balance
) -> float:
    """s for the owner (40.3): a seat holder its seat score for its seat's areas, the CEO its
    CEO score, anyone else the area's weights over true skills. Never shown."""
    kind = owner_kind(state, company_id, area, person_id, b)
    a = area_def(b, area)
    skills = state.person(person_id).skills.as_dict()
    if kind == "seat" and a.seat is not None:
        return true_score(state, person_id, a.seat, b)
    if kind in ("ceo", "subsidiary_ceo"):
        return ceo_score(skills, dict(b.ceo.weights))
    return sum(w * skills[k] for k, w in a.weights.items())


def shown_area_score(
    state: GameState, company_id: int, area: str, person_id: int, b: Balance
) -> float:
    """The same from the company's displayed ranges' midpoints (18.8): what the player sees."""
    kind = owner_kind(state, company_id, area, person_id, b)
    a = area_def(b, area)
    if kind == "seat" and a.seat is not None:
        return displayed_score(state, company_id, person_id, a.seat, b)
    reveal = state.reveal(company_id, person_id)
    if reveal is None:
        return NEUTRAL_SCORE
    person = state.person(person_id)
    weights = dict(b.ceo.weights) if kind in ("ceo", "subsidiary_ceo") else a.weights
    total = 0.0
    for key, w in weights.items():
        lo, hi = revealed_range(person, reveal, key)
        total += w * (lo + hi) / 2
    return total


def fit_band(score: float, b: Balance) -> str:
    """18.8's fit words for a displayed score."""
    bands = b.exec_seats.fit_bands
    if score < bands.lo:
        return FIT_WORDS[0]
    return FIT_WORDS[2] if score >= bands.hi else FIT_WORDS[1]


def default_limit(cash: Cents, b: Balance) -> int:
    """default_limit_bp of cash, rounded down to limit_round_cents, at least min_limit_cents
    (40.2)."""
    ab = b.automation
    raw = max(0, cash) * ab.default_limit_bp // BP_DENOMINATOR
    return max(ab.min_limit_cents, raw // ab.limit_round_cents * ab.limit_round_cents)


def valid_owner(state: GameState, owner: AreaOwner, b: Balance) -> bool:
    """The owner still may own the area (still employed, still in the seat or role)."""
    return owner_kind(state, owner.company_id, owner.area, owner.person_id, b) is not None
