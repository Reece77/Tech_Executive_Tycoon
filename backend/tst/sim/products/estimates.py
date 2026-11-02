"""A product team as the player can judge it (formulas.md 23.4, M10b; ADR-0007).

The engine's team output and seller capacity come from true skills and tags, which stay
hidden. The numbers the player sees (the team-strength line, the slipping and capacity notes)
use the same team with each builder's development skill and each seller's selling skill taken
from the midpoints of the ranges the company sees, and only the tags it has noticed. Seat and
event multipliers are kept: the API computes the team with seat estimates already (18.8).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, CategoryDef
from tst.sim.people.reveal import revealed_range
from tst.sim.products import formulas as f
from tst.sim.products.team import Contributor, Team
from tst.sim.state import GameState

SELL_SKILLS = ("sales", "negotiation", "communication")


def _shown_skills(state: GameState, company_id: int, person_id: int) -> dict[str, float] | None:
    """Midpoints of the displayed ranges; None for the founder (they know themselves) or with
    no record (the true values are then used: nothing is known that would differ)."""
    person = state.person(person_id)
    reveal = state.reveal(company_id, person_id)
    if person.is_founder or reveal is None:
        return None
    return {k: sum(revealed_range(person, reveal, k)) / 2 for k in person.skills.as_dict()}


def _known_tags(state: GameState, company_id: int, person_id: int) -> tuple[str, ...]:
    person = state.person(person_id)
    reveal = state.reveal(company_id, person_id)
    if person.is_founder or reveal is None:
        return person.tags
    return tuple(tag for tag, _ in reveal.revealed_tags)


def shown_team(
    state: GameState, company_id: int, team: Team, category: CategoryDef, balance: Balance
) -> Team:
    """`team` with every builder's output and seller's contribution re-scaled from what the
    company sees: x (shown d x shown t) / (true d x true t) and x shown sell / true sell."""
    pb = balance.products
    builders = []
    for b in team.builders:
        shown = _shown_skills(state, company_id, b.person_id)
        person = state.person(b.person_id)
        true = f.dev_skill(person.skills.as_dict(), category.dev_weights) * f.tag_multiplier(
            person.tags, pb
        )
        seen = (
            f.dev_skill(shown, category.dev_weights) if shown is not None else b.d
        ) * f.tag_multiplier(_known_tags(state, company_id, b.person_id), pb)
        builders.append(replace(b, output=b.output * (seen / true if true else 1.0)))
    sellers = []
    for s in team.sellers:
        shown = _shown_skills(state, company_id, s.person_id)
        if shown is None:
            sellers.append(s)
            continue
        skills = state.person(s.person_id).skills
        true_sell = f.sell_skill(*(skills[k] for k in SELL_SKILLS))
        seen_sell = f.sell_skill(*(shown[k] for k in SELL_SKILLS))
        factor = seen_sell / true_sell if true_sell else 1.0
        sellers.append(Contributor(s.person_id, s.contribution * factor))
    return replace(team, builders=tuple(builders), sellers=tuple(sellers))
