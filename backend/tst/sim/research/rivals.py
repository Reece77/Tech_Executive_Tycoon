"""Rivals research (docs/formulas.md 21.6): incumbents' `research` action and its months.

The action is scored with the rest of 15.3 on stream `rivals` (its candidates come last, so
earlier draws are unchanged). While it runs, a research project without a unit raises the
rival's lead by rnd.rival.rate x builder_skill / 10 a month and its builder pool is
rnd.rival.pool_cost larger. Breakthroughs: stream `rival_research` (24), key
`(company_id,)`, one uniform a month, with the player's probability. Startups do not research.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from tst.sim.data_models import Balance, GameData
from tst.sim.research import levels
from tst.sim.research.models import ResearchProject
from tst.sim.research.projects import add_lead, quality
from tst.sim.rivals.models import stream_key
from tst.sim.rng import RngFactory
from tst.sim.state import CompanyState, GameState, with_pool, with_research_project

RESEARCH = "research"  # the rival action's name (15.3, 21.6)


@dataclass(frozen=True, slots=True)
class ResearchNeed:
    domain: str
    need: float


def rival_domains(state: GameState, data: GameData, company_id: int) -> tuple[str, ...]:
    """Domains that feed the categories of the rival's live products, in data order."""
    cats = {p.category for p in state.company_products(company_id) if p.status == "live"}
    return tuple(d for d in levels.domain_keys(data) if set(levels.feeds(data, d)) & cats)


def research_needs(
    state: GameState, company: CompanyState, balance: Balance, data: GameData
) -> list[ResearchNeed]:
    """need = (best lead in the domain - own) / need_span, + era_bonus when one of the
    domain's eras is within era_window_months of its historical date and not here yet,
    clamped to 0-1 (21.6). Empty for startups and rivals without products."""
    if company.is_startup or data.tech is None:
        return []
    rv = balance.rnd.rival
    out: list[ResearchNeed] = []
    for domain in rival_domains(state, data, company.id):
        best = max((r.lead for r in state.research_leads if r.domain == domain), default=0.0)
        need = (best - state.research_lead(company.id, domain)) / rv.need_span
        for era in levels.eras_in(data, domain):
            months = levels.historical_turn(era) - state.turn
            if state.era_arrival(era.key) is None and 0 <= months <= rv.era_window_months:
                need += rv.era_bonus
                break
        out.append(ResearchNeed(domain, max(0.0, min(1.0, need))))
    return out


def researching(state: GameState, company_id: int) -> bool:
    return any(p.unit_id is None for p in state.active_projects(company_id))


def start_research(
    state: GameState, company: CompanyState, domain: str, balance: Balance, data: GameData
) -> tuple[GameState, str]:
    """The research action (21.6): a unit-less project for rnd.rival.months and a builder
    pool rnd.rival.pool_cost larger while it runs."""
    rv = balance.rnd.rival
    project_id, ids = state.next_ids.take("research_project")
    project = ResearchProject(
        id=project_id,
        company_id=company.id,
        domain=domain,
        unit_id=None,
        start_turn=state.turn,
        end_turn=state.turn + rv.months - 1,
    )
    state = with_research_project(replace(state, next_ids=ids), project)
    state = _scale_builders(state, company.id, 1 + rv.pool_cost)
    return state, f"started {levels.domain_def(data, domain).label} research"


def _scale_builders(state: GameState, company_id: int, factor: float) -> GameState:
    for pool in state.company_pools(company_id):
        if pool.function == "builder":
            state = with_pool(state, replace(pool, headcount=pool.headcount * factor))
    return state


def month_start(state: GameState, balance: Balance) -> GameState:
    """Phase 1: a rival research action that ended last month returns its extra builders,
    so its last month's payroll paid the premium too (21.6; M12r)."""
    for project in state.research_projects:
        if project.unit_id is not None or project.status != "stopped":
            continue
        if project.end_turn != state.turn - 1 or not state.company(project.company_id).alive:
            continue
        state = _scale_builders(state, project.company_id, 1 / (1 + balance.rnd.rival.pool_cost))
    return state


def rival_research_month(state: GameState, rng: RngFactory, balance: Balance) -> GameState:
    """Phase 3: each running rival research action, by project id, adds its monthly lead and
    draws for a breakthrough; one that ends this month keeps its extra builders through this
    month's payroll and returns them at the start of the next (`month_start`; 21.6, M12r)."""
    rnd = balance.rnd
    for project in state.active_projects():
        if project.unit_id is not None:
            continue
        company = state.company(project.company_id)
        if not company.alive:
            state = with_research_project(state, replace(project, status="stopped"))
            continue
        skill = company.builder_skill or 0.0
        gained = rnd.rival.rate * skill / 10  # tunable-exempt: d / 10, as for builders (11.3)
        key = stream_key(company.id, company.rival_key)  # ADR-0013 amendment (M12a)
        gen = rng.stream(state.turn, "rival_research", *key)
        event = None
        if float(gen.random()) < rnd.breakthrough_chance * quality(skill, balance):
            gained += rnd.breakthrough_points
            event = "breakthrough"
        state = add_lead(state, company.id, project.domain, gained)
        done = project.end_turn is not None and state.turn >= project.end_turn
        updated = replace(
            project,
            gained=project.gained + gained,
            recent=(*project.recent, gained)[-rnd.progress_window :],
            status="stopped" if done else "active",
            last_event=event or project.last_event,  # type: ignore[arg-type]
            last_event_turn=state.turn if event else project.last_event_turn,
        )
        state = with_research_project(state, updated)
    return state
