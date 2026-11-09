"""The legacy score (docs/formulas.md 32.6, M24): at the game's end and in the Hall of Fame.
`legacy = best company score reached (30.1) + 100 x log10(1 + lifetime grants / $1M)
+ 2 x (Visionary + Beloved) - (Ruthless + Reckless)`, across a serial founder's companies,
plus M26's wealth term `personal.legacy_points x log10(1 + net worth / unit)` (37.5) from the
last month-end net worth."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from tst.sim.data_models import Balance
from tst.sim.state import GameState, foundation_of, life_of

GIVING_POINTS: Final = 100  # 32.6's formula constant: points per decade of lifetime grants
GOOD_WEIGHT: Final = 2  # 32.6's formula constant: Visionary and Beloved count twice
CENTS_A_DOLLAR: Final = 100  # tunable-exempt: cents in a dollar


@dataclass(frozen=True, slots=True)
class Legacy:
    total: int
    best_score: int
    best_company_id: int | None
    giving: float
    persona: float
    grants_cents: int
    wealth: float = 0.0  # M26 (37.5)
    net_worth_cents: int = 0


def founder_companies(state: GameState) -> tuple[int, ...]:
    """Every company the player's founder has run: the ventures, then the current one."""
    return (*(v.company_id for v in state.ventures), state.player.id)


def legacy_parts(
    best_score: int, grants_cents: int, traits: tuple[float, float, float, float], balance: Balance
) -> tuple[float, float]:
    """(giving, persona) parts; traits in config.TRAITS order."""
    unit = balance.foundation.legacy_unit_dollars * CENTS_A_DOLLAR
    giving = GIVING_POINTS * math.log10(1 + grants_cents / unit)
    visionary, ruthless, beloved, reckless = traits
    return giving, GOOD_WEIGHT * (visionary + beloved) - (ruthless + reckless)


def legacy_of(state: GameState, balance: Balance) -> Legacy:
    ids = set(founder_companies(state))
    scored = [s for s in state.scores if s.company_id in ids]
    best = max(scored, key=lambda s: (s.score, -s.turn), default=None)
    founder = state.founder_of(state.player.id)
    person_id = founder.id if founder is not None else None
    if person_id is None:  # after an exit the founder's employment has ended
        person_id = next((life.person_id for life in state.founder_lives), None)
    life = life_of(state, person_id) if person_id is not None else None
    foundation = foundation_of(state, person_id) if person_id is not None else None
    grants = foundation.grants_cents if foundation is not None else 0
    start = balance.persona.start
    traits = (
        (life.visionary, life.ruthless, life.beloved, life.reckless)
        if life is not None
        else (start, start, start, start)
    )
    best_score = best.score if best is not None else 0
    giving, persona = legacy_parts(best_score, grants, traits, balance)
    from tst.sim.founder.wealth import legacy_wealth

    points = [w for w in state.wealth_points if w.person_id == person_id]
    worth = points[-1].total_cents if points else 0
    wealth = legacy_wealth(worth, balance)
    return Legacy(
        total=round(best_score + giving + persona + wealth),
        best_score=best_score,
        best_company_id=best.company_id if best is not None else None,
        giving=giving,
        persona=persona,
        grants_cents=grants,
        wealth=wealth,
        net_worth_cents=worth,
    )
