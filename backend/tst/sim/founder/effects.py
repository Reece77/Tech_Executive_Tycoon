"""What the founder's persona and foundation change elsewhere (docs/formulas.md 32.3, 32.4),
as small queries the other systems call. A founder whose traits stay below
persona.effect_at and who has no foundation changes nothing (32.7 target 1)."""

from __future__ import annotations

from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.founder.models import Foundation
from tst.sim.founder.persona import strong
from tst.sim.geo.cities import hq_city
from tst.sim.state import GameState, foundation_of

CENTS_A_DOLLAR: Final = 100  # tunable-exempt: cents in a dollar

BUILDER = "builder"  # roles.yaml product_function


def hiring_points(
    state: GameState, company_id: int, role: str | None, balance: Balance, data: GameData
) -> float:
    """Offer-score points: Visionary's for builder roles; education grants' in the
    foundation's region (the company's HQ there)."""
    points = 0.0
    if (
        role is not None
        and role != "founder"
        and strong(state, company_id, "visionary", balance)
        and data.role(role).product_function == BUILDER
    ):
        points += balance.persona.builder_hiring
    region = education_region(state, company_id, balance)
    if region is not None:
        company = state.company(company_id)
        if data.city(hq_city(company, balance)).region == region:
            points += education_points(state, company_id, balance)
    return points


def morale_points(state: GameState, company_id: int, balance: Balance) -> float:
    """Morale-target points for staff: Ruthless's cost, health grants' gain."""
    points = health_points(state, company_id, balance)
    if strong(state, company_id, "ruthless", balance):
        points += balance.persona.ruthless_morale
    return points


def resign_factor(state: GameState, company_id: int, balance: Balance) -> float:
    """Beloved: resignations x persona.resign_mult."""
    return balance.persona.resign_mult if strong(state, company_id, "beloved", balance) else 1.0


def feud_factor(state: GameState, company_id: int, balance: Balance) -> float:
    """Ruthless: rival feuds build x persona.feud_mult."""
    return balance.persona.feud_mult if strong(state, company_id, "ruthless", balance) else 1.0


def cred_target(state: GameState, company_id: int, balance: Balance) -> float:
    """Reckless: credibility drifts toward persona.reckless_cred_target, not cred_start."""
    if strong(state, company_id, "reckless", balance):
        return balance.persona.reckless_cred_target
    return balance.press.cred_start


def consumer_brand(state: GameState, company_id: int, balance: Balance) -> float:
    """Climate grants: brand-target points on consumer products."""
    return climate_points(state, company_id, balance)


def pool_bonus(state: GameState, company_id: int, balance: Balance) -> float:
    """Local grants: the share added to hiring pools when the company's HQ is the
    foundation's city."""
    city = pool_city(state, company_id, balance)
    if city is None or city != hq_city(state.company(company_id), balance):
        return 0.0
    return balance.foundation.pool


# --- The foundation's running grant effects (32.3) ------------------------------------------


def _active(state: GameState, company_id: int, cause: str, balance: Balance) -> Foundation | None:
    """The company founder's foundation if its last grants' `cause` effect is running."""
    founder = state.founder_of(company_id)
    if founder is None:
        return None
    f = foundation_of(state, founder.id)
    if f is None or f.cause != cause or f.last_grant_turn is None:
        return None
    if not f.last_grant_turn <= state.turn < f.last_grant_turn + balance.foundation.effect_months:
        return None
    return f


def education_points(state: GameState, company_id: int, balance: Balance) -> float:
    """Education: offer-score points, foundation.hiring at most, scaled by the year's grants
    up to foundation.hiring_full_dollars, while the company's HQ is in the foundation's region
    (the founder's home region when it was created)."""
    fb = balance.foundation
    f = _active(state, company_id, "education", balance)
    if f is None:
        return 0.0
    return fb.hiring * min(1.0, f.last_grant_cents / CENTS_A_DOLLAR / fb.hiring_full_dollars)


def education_region(state: GameState, company_id: int, balance: Balance) -> str | None:
    f = _active(state, company_id, "education", balance)
    return f.region if f is not None else None


def climate_points(state: GameState, company_id: int, balance: Balance) -> float:
    """Climate: brand-target points on consumer products."""
    return balance.foundation.brand if _active(state, company_id, "climate", balance) else 0.0


def health_points(state: GameState, company_id: int, balance: Balance) -> float:
    """Health: staff morale-target points."""
    return balance.foundation.morale if _active(state, company_id, "health", balance) else 0.0


def pool_city(state: GameState, company_id: int, balance: Balance) -> str | None:
    """Local communities: the city whose hiring pools grow by foundation.pool."""
    f = _active(state, company_id, "local", balance)
    return f.city if f is not None else None
