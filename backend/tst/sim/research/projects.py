"""Research projects (docs/formulas.md 21.3) and lead decay (21.1), phase 3.

A project is an org unit working on a domain instead of a product. Its researchers are the
unit's direct members with a builder role (and the founder), as on a product team (11.3).

Randomness: stream `research` (23), key `(project_id,)`, two uniform draws a month for each
active project with output, in project id order: breakthrough, then dead end (only drawn on
when there was no breakthrough).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from tst.sim.data_models import Balance, GameData
from tst.sim.events import modifiers as mf
from tst.sim.finance import macro
from tst.sim.ledger import CASH, RESEARCH, LedgerEntry
from tst.sim.org.rules import OrgView, org_view
from tst.sim.org.scaleup import modifiers
from tst.sim.people.reveal import revealed_range
from tst.sim.products import formulas as pf
from tst.sim.research import levels
from tst.sim.research.data import DomainDef
from tst.sim.research.models import ResearchLead, ResearchProject
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_research_lead, with_research_project

ATTR_NEUTRAL = 10  # tunable-exempt: r_i / 10, as d_i / 10 for builders (11.3)


@dataclass(frozen=True, slots=True)
class Researcher:
    person_id: int
    skill: float  # r_i: the domain's research skill
    output: float  # r_i / 10 x m_i x lambda_i


@dataclass(frozen=True, slots=True)
class Lab:
    """A project's researchers this month and what they need (21.3)."""

    researchers: tuple[Researcher, ...]
    output: float  # o = coord(n) x sum, before funding
    needed_cents: int  # full funding this month
    budget_cents: int  # what the project will spend: min(budget, needed)

    @property
    def funded(self) -> float:
        return 1.0 if self.needed_cents <= 0 else min(1.0, self.budget_cents / self.needed_cents)

    @property
    def funded_output(self) -> float:
        return self.output * self.funded

    @property
    def mean_skill(self) -> float:
        n = len(self.researchers)
        return sum(r.skill for r in self.researchers) / n if n else 0.0


def research_skill(skills: Mapping[str, float], domain: DomainDef) -> float:
    """r_i = sum of the domain's research-skill weights x skills (21.3)."""
    return sum(w * skills[k] for k, w in domain.research_skill.items())


def researcher_cost_cents(state: GameState, data: GameData, domain: DomainDef) -> int:
    """A researcher's monthly budget (21.3); x the AI compute index for an indexed domain."""
    if domain.compute_indexed:
        return round(domain.budget_cents * macro.ai_index(state, data))
    return domain.budget_cents


def _shown_skills(state: GameState, company_id: int, person_id: int) -> dict[str, float]:
    """A researcher's skills as the company sees them: the midpoints of its displayed ranges
    (23.4); a founder, or someone it has no reveal record of, at true values."""
    person = state.person(person_id)
    reveal = state.reveal(company_id, person_id)
    if person.is_founder or reveal is None:
        return person.skills.as_dict()
    return {k: sum(revealed_range(person, reveal, k)) / 2 for k in person.skills.as_dict()}


def _known_tags(state: GameState, company_id: int, person_id: int) -> tuple[str, ...]:
    """The tags the company has noticed (23.4); a founder's or an unrecorded person's all."""
    person = state.person(person_id)
    reveal = state.reveal(company_id, person_id)
    if person.is_founder or reveal is None:
        return person.tags
    return tuple(tag for tag, _ in reveal.revealed_tags)


def lab(
    state: GameState,
    view: OrgView,
    project: ResearchProject,
    balance: Balance,
    data: GameData,
    *,
    estimate: bool = False,
) -> Lab:
    """Who researches on a project and their output (21.3): coord(n) x sum (r_i / 10) x m_i x
    lambda_i, lambda_i the tags' and seats' factors on builders (11.10, 18.5).

    `estimate`: the lab as the company sees it, for the API (21.7, 21.10; M12r): research
    skills from displayed ranges, only noticed tags, and executive seat factors from
    displayed ranges (`modifiers(..., estimate=True)`, 18.8). The engine uses true values."""
    pb = balance.products
    domain = levels.domain_def(data, project.domain)
    cid = project.company_id
    mods = modifiers(state, view, balance, data, estimate=estimate)
    out: list[Researcher] = []
    members = view.members.get(project.unit_id, ()) if project.unit_id is not None else ()
    # event modifiers on the unit's builder output (M10b, 23.2) count for research too
    unit_factor = (
        mf.unit_factor(state, project.company_id, project.unit_id, "builder_output")
        if project.unit_id is not None
        else 1.0
    )
    for person_id in members:
        person = state.person(person_id)
        if not person.is_founder:
            employment = state.employment_of(person_id)
            if employment is None or data.role(employment.role).product_function != "builder":
                continue
        m = pf.morale_factor(state.person_state(person_id).morale, pb)
        tags = _known_tags(state, cid, person_id) if estimate else person.tags
        lam = pf.tag_multiplier(tags, pb) * (mods.builder.get(person_id, 1.0) if mods else 1.0)
        lam *= unit_factor
        skills = _shown_skills(state, cid, person_id) if estimate else person.skills.as_dict()
        r = research_skill(skills, domain)
        out.append(Researcher(person_id, r, r / ATTR_NEUTRAL * m * lam))
    output = pf.coord_factor(len(out), pb) * sum(r.output for r in out) if out else 0.0
    needed = len(out) * researcher_cost_cents(state, data, domain)
    budget = needed if project.budget_cents is None else min(project.budget_cents, needed)
    return Lab(tuple(out), output, needed, budget)


def progress(output: float, current_lead: float, balance: Balance) -> float:
    """Delta R = rnd.rate x o / (1 + R / rnd.half) (21.3)."""
    rnd = balance.rnd
    return rnd.rate * output / (1 + current_lead / rnd.half)


def quality(mean_skill: float, balance: Balance) -> float:
    """q = clamp(mean research skill / 12, 0.5, 1.5) (21.3)."""
    lo, hi = balance.rnd.quality_clamp
    return max(lo, min(hi, mean_skill / balance.rnd.quality_skill))


def add_lead(state: GameState, company_id: int, domain: str, delta: float) -> GameState:
    """The company's lead in the domain + delta, never below 0."""
    current = state.research_lead(company_id, domain)
    return with_research_lead(state, ResearchLead(company_id, domain, max(0.0, current + delta)))


def run_projects(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    """Phase 3 (21.3): each active project with a unit, by id, spends its budget, gains
    lead and draws for a breakthrough and a dead end. A project whose unit is gone stops."""
    rnd = balance.rnd
    entries: list[LedgerEntry] = []
    views: dict[int, OrgView] = {}
    for project in state.active_projects():
        if project.unit_id is None:
            continue  # a rival's research action (21.6), run by research.rivals
        unit = state.unit(project.unit_id)
        if unit is None or unit.status != "active" or not state.company(project.company_id).alive:
            state = with_research_project(
                state, replace(project, status="stopped", end_turn=state.turn)
            )
            continue
        cid = project.company_id
        view = views.setdefault(cid, org_view(state, cid))
        work = lab(state, view, project, balance, data)
        if work.budget_cents > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=cid,
                    memo=f"Research: {levels.domain_def(data, project.domain).label}",
                    debit=RESEARCH,
                    credit=CASH,
                    amount=work.budget_cents,
                )
            )
        gained = progress(work.funded_output, state.research_lead(cid, project.domain), balance)
        event: str | None = None
        if work.funded_output > 0:
            gen = rng.stream(state.turn, "research", project.id)
            q = quality(work.mean_skill, balance)
            if float(gen.random()) < rnd.breakthrough_chance * q:
                event = "breakthrough"
                gained += rnd.breakthrough_points
            elif float(gen.random()) < rnd.dead_end_chance / q:
                event = "dead_end"
        recent = (*project.recent, gained)[-rnd.progress_window :]
        if event == "dead_end":
            lost = rnd.dead_end_share * sum(recent)
            gained -= lost
            recent = (*recent[:-1], recent[-1] - lost)
        state = add_lead(state, cid, project.domain, gained)
        state = with_research_project(
            state,
            replace(
                project,
                recent=recent,
                gained=project.gained + gained,
                last_event=event if event else project.last_event,  # type: ignore[arg-type]
                last_event_turn=state.turn if event else project.last_event_turn,
            ),
        )
    return state, tuple(entries)


def decay_leads(state: GameState, data: GameData, balance: Balance) -> GameState:
    """R <- R x (1 - rnd.decay) for every lead, after progress (21.1); a first mover's lead
    in its era's domain does not decay during its window (21.4)."""
    if not state.research_leads:
        return state
    keep = 1 - balance.rnd.decay
    held: dict[int, set[str]] = {}
    for era in data.eras.eras:
        a = state.era_arrival(era.key)
        if (
            a is not None
            and a.company_id is not None
            and a.turn <= state.turn < a.turn + balance.rnd.first_mover_months
        ):
            held.setdefault(a.company_id, set()).add(era.domain)
    leads = tuple(
        r if r.domain in held.get(r.company_id, set()) else replace(r, lead=r.lead * keep)
        for r in state.research_leads
    )
    return replace(state, research_leads=leads)
