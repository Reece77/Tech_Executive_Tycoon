"""Every term of one employee's morale target (formulas.md sections 9 and 13).

Phase 8 uses these true terms. The API builds the player's breakdown from them and hides
whatever the company cannot know (13.11), so the arithmetic lives in one place.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tst.sim.data_models import Balance, GameData
from tst.sim.hiring.formulas import fit_term, market_mid_cents, pay_term, runway_term
from tst.sim.hiring.rules import matching_interests
from tst.sim.money import Cents
from tst.sim.org.relationships import unit_mate_values
from tst.sim.org.rules import OrgView, manager_terms, remote_morale, teammate_terms
from tst.sim.org.scaleup import support_morale_terms
from tst.sim.people.models import Employment
from tst.sim.people.relationships import relationship_morale
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class MoraleTerms:
    base: float
    pay: float
    fit: float
    runway: float
    workload: float
    manager: float
    team: tuple[tuple[str, int, float], ...]  # (tag, holders, term) per morale tag (13.6)
    remote: float
    relationships: float = 0.0  # W_rel (M6, 16.7)
    support: float = 0.0  # W_support, "Admin and support" (M8, 18.4)
    crowded: float = 0.0  # "Crowded office" (M9, 19.2)

    @property
    def team_total(self) -> float:
        return sum(term for _, _, term in self.team)

    @property
    def target(self) -> float:
        """target = 50 + P + F + W_runway + W_load + W_mgr + W_team + W_remote + W_rel
        (sections 9 and 16.7)."""
        return (
            self.base
            + self.pay
            + self.fit
            + self.runway
            + self.workload
            + self.manager
            + self.team_total
            + self.remote
            + self.relationships
            + self.support
            + self.crowded
        )


def market_mid_for(
    state: GameState, employment: Employment, balance: Balance, data: GameData
) -> Cents:
    """The role and level's band mid x the multiplier of the city they work in (2, 19.1)."""
    from tst.sim.geo.cities import work_multiplier_bp

    role = data.role(employment.role)
    return market_mid_cents(
        role.salary_band_mid_cents[employment.level],
        work_multiplier_bp(state, employment, balance, data),
    )


def morale_terms(
    state: GameState,
    view: OrgView,
    employment: Employment,
    balance: Balance,
    data: GameData,
    opening_cash: Cents,
    current_cash: Cents,
    support: Mapping[int, float] | None = None,
    crowded: set[int] | None = None,
) -> MoraleTerms:
    """True terms for an employee (not the founder), using `view` for reporting lines.
    `support` is W_support by person (18.4), and `crowded` the people in an overfull
    office (19.2), computed here when not given."""
    from tst.sim.geo.offices import crowded_people

    if crowded is None:
        crowded = crowded_people(state, employment.company_id)
    cfg = balance.morale
    person = state.person(employment.person_id)
    company = state.company(employment.company_id)
    role = data.role(employment.role)
    return MoraleTerms(
        base=cfg.target_base,
        pay=pay_term(
            employment.salary_cents, market_mid_for(state, employment, balance, data), cfg
        ),
        fit=fit_term(
            matching_interests(person, company.mission),
            style_mismatch=person.work_style != role.work_style,
            morale=cfg,
        ),
        runway=runway_term(opening_cash, current_cash, cfg),
        workload=cfg.workload_term,
        manager=manager_terms(state, view, person.id, balance).morale,
        team=teammate_terms(state, view, person.id, balance),
        remote=remote_morale(state, employment, balance),
        relationships=relationship_morale(
            unit_mate_values(state, view, person.id), balance.relationships
        ),
        support=(
            support if support is not None else support_morale_terms(state, view, balance, data)
        ).get(person.id, 0.0),
        crowded=balance.office.crowded_morale if person.id in crowded else 0.0,
    )
