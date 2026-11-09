"""The exploration pipeline (docs/formulas.md 34.2-34.4): desk studies, licences, survey,
sampling, drilling, resource estimates, feasibility, permitting and selling a project.

Actions (ADR-0014) start a stage and pay for it; the monthly phase (phase 4) reports stages
that are due, drills the month's holes, and runs permits. Every draw is on stream
`exploration` keyed by what it belongs to (ADR-0013), never by iteration order. What a stage
reveals is stored on the project and is a function of the hidden truth plus noise; every
estimate the API shows is then computed from those revealed numbers only (34.5)."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import (
    ExplorationRuleError,
    InsufficientCashError,
    InvalidActionError,
    UnknownExplorationProjectError,
)
from tst.sim.exploration import formulas as xf
from tst.sim.exploration.config import CATEGORIES, LEVELS, GeoCommodity
from tst.sim.exploration.geology import GEOLOGY_TURN, block_of, cell_deviations
from tst.sim.exploration.m17 import buyers_of, deck, usd_per_tonne
from tst.sim.exploration.models import (
    GEOLOGY_STAGES,
    DeskStudy,
    GeoBlock,
    Hole,
    Project,
    SupplierLicence,
)
from tst.sim.ledger import CASH, DISPOSAL, EXPLORATION, LedgerBalances, LedgerEntry
from tst.sim.log import inbox_item
from tst.sim.money import format_money
from tst.sim.rng import RngFactory
from tst.sim.state import (
    CompanyState,
    GameState,
    company_cash,
    group_companies,
    holding_of,
)

LINK: Final = "exploration"
MONTHS_A_YEAR: Final = 12  # tunable-exempt: calendar
PERM_TAG: Final = 3  # geology key (region, block, 3): the order holes visit the ore body
MIN_PERMIT_MONTHS: Final = 6  # tunable-exempt: a permit decision never comes sooner
TRACE_TONNAGE: Final = 0.05  # tunable-exempt: a background envelope, x the commodity's median
EVENT_TEMPLATES: Final = ("community_blockade", "permit_challenge")
DESK, SURVEY, SAMPLE, HOLE, ESTIMATE, STUDY, PERMIT, PROTEST, SALE, MINOR = range(10)

type StageName = Literal[
    "survey", "sampling", "estimate", "scoping", "pre_feasibility", "definitive", "permitting"
]


# --- Actions --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StartDeskStudy:
    actor_id: int
    region: str
    commodity: str
    company_id: int | None = None  # a group company; default the actor's
    kind: Literal["start_desk_study"] = "start_desk_study"


@dataclass(frozen=True, slots=True)
class TakeLicence:
    actor_id: int
    region: str
    block: int
    company_id: int | None = None
    kind: Literal["take_licence"] = "take_licence"


@dataclass(frozen=True, slots=True)
class RenewLicence:
    actor_id: int
    project_id: int
    kind: Literal["renew_licence"] = "renew_licence"


@dataclass(frozen=True, slots=True)
class StartStage:
    """Start a survey, sampling, a resource estimate, a feasibility study (by level) or the
    permit application. `commodity`: what sampling looks for (default: the anomaly's)."""

    actor_id: int
    project_id: int
    stage: StageName
    commodity: str | None = None
    kind: Literal["start_stage"] = "start_stage"


@dataclass(frozen=True, slots=True)
class OrderDrilling:
    actor_id: int
    project_id: int
    holes: int
    kind: Literal["order_drilling"] = "order_drilling"


@dataclass(frozen=True, slots=True)
class SellProject:
    actor_id: int
    project_id: int
    kind: Literal["sell_project"] = "sell_project"


@dataclass(frozen=True, slots=True)
class RelinquishProject:
    actor_id: int
    project_id: int
    kind: Literal["relinquish_project"] = "relinquish_project"


type ExplorationAction = (
    StartDeskStudy
    | TakeLicence
    | RenewLicence
    | StartStage
    | OrderDrilling
    | SellProject
    | RelinquishProject
)

ACTION_TYPES: Final[dict[str, type]] = {
    "start_desk_study": StartDeskStudy,
    "take_licence": TakeLicence,
    "renew_licence": RenewLicence,
    "start_stage": StartStage,
    "order_drilling": OrderDrilling,
    "sell_project": SellProject,
    "relinquish_project": RelinquishProject,
}


# --- Who explores, and with whom --------------------------------------------------------------


def explorers(state: GameState) -> tuple[CompanyState, ...]:
    """The player's group: the operating company, a holding company and its subsidiaries."""
    held = holding_of(state)
    top = held.company_id if held is not None else state.player.id
    return group_companies(state, top)


def gate(state: GameState, company: CompanyState, balance: Balance) -> list[str]:
    """34.4: a company at stage 3 or more explores; a group company counts its group's stage."""
    stage = max(c.stage for c in explorers(state))
    if max(company.stage, stage) < balance.exploration.min_stage:
        return [f"exploration opens at stage {balance.exploration.min_stage}"]
    return []


def _company(
    state: GameState, actor_id: int, company_id: int | None, balance: Balance
) -> CompanyState:
    founder = state.founder_of(state.player.id)
    employment = state.employment_of(actor_id)
    is_founder = founder is not None and founder.id == actor_id
    if not is_founder and employment is None:
        raise InvalidActionError(f"person {actor_id} cannot act for the company")
    cid = company_id
    if cid is None:
        cid = employment.company_id if employment is not None else state.player.id
    ids = {c.id for c in explorers(state)}
    if cid not in ids:
        raise ExplorationRuleError("only the player's group explores")
    if not is_founder and (employment is None or employment.company_id != cid):
        raise InvalidActionError("only the founder acts for another group company")
    company = state.company(cid)
    if reasons := gate(state, company, balance):
        raise ExplorationRuleError("; ".join(reasons))
    return company


def geologists(state: GameState, company_id: int, balance: Balance) -> tuple[int, ...]:
    role = balance.exploration.geologist_role
    return tuple(e.person_id for e in state.staff(company_id) if e.role == role)


def team_skills(state: GameState, company_id: int, balance: Balance) -> tuple[float, float]:
    """The team's field skill (mean geology) and estimation skill (mean of geology and data):
    34.2's skill, from the true skills (the sim's own reading; the API shows only the range
    factor's effect, never a skill)."""
    people = [state.person(p).skills.as_dict() for p in geologists(state, company_id, balance)]
    if not people:
        return 0.0, 0.0
    field = sum(s["geology"] for s in people) / len(people)
    est = sum((s["geology"] + s["data"]) / 2 for s in people) / len(people)
    return field, est


def factors(state: GameState, company_id: int, balance: Balance) -> tuple[float, float]:
    field, est = team_skills(state, company_id, balance)
    eb = balance.exploration
    return xf.range_factor(field, eb), xf.range_factor(est, eb)


def reading_factor(state: GameState, company_id: int, balance: Balance) -> float:
    """A desk study's or a survey's noise factor (34.2, M18 decision): reading a region or an
    anomaly compounds two judgements, the field geology and the data (geophysics), so the noise
    is x both range factors."""
    field, est = factors(state, company_id, balance)
    return field * est


def busy_count(state: GameState, company_id: int) -> int:
    studies = sum(1 for d in state.desk_studies if d.company_id == company_id and not d.done)
    return studies + sum(1 for p in state.projects if p.company_id == company_id and p.busy)


def _need_geologist(state: GameState, company_id: int, balance: Balance) -> None:
    n = len(geologists(state, company_id, balance))
    if n == 0:
        raise ExplorationRuleError("hire a geologist first")
    if busy_count(state, company_id) >= n * balance.exploration.stages_per_geologist:
        raise ExplorationRuleError(f"all {n} geologists are busy")


def _pay(
    state: GameState,
    company_id: int,
    cents: int,
    memo: str,
    balances: LedgerBalances,
) -> tuple[LedgerEntry, ...]:
    if cents <= 0:
        return ()
    if company_cash(balances, company_id) < cents:
        raise InsufficientCashError(f"{memo} needs {format_money(cents)} in cash")
    return (
        LedgerEntry.transfer(
            turn=state.turn,
            company_id=company_id,
            memo=memo,
            debit=EXPLORATION,
            credit=CASH,
            amount=cents,
        ),
    )


def _energy(state: GameState, actor_id: int, kind: str, balance: Balance, cost: int) -> GameState:
    return spend_energy(state, actor_id, kind, balance, cost=cost)


def _commodity(data: GameData, key: str) -> GeoCommodity:
    if data.geology is None or key not in data.geology.keys:
        raise ExplorationRuleError(f"{key!r} is not an explored commodity")
    return data.geology.commodity(key)


def _region(data: GameData, region: str) -> int:
    if region not in data.region_keys:
        raise ExplorationRuleError(f"unknown region {region!r}")
    return data.region_keys.index(region)


def project_of(state: GameState, project_id: int) -> Project:
    for p in state.projects:
        if p.id == project_id:
            return p
    raise UnknownExplorationProjectError(f"no exploration project {project_id}")


def with_project(state: GameState, project: Project) -> GameState:
    others = tuple(p for p in state.projects if p.id != project.id)
    return replace(state, projects=tuple(sorted((*others, project), key=lambda p: p.id)))


def with_study(state: GameState, study: DeskStudy) -> GameState:
    others = tuple(d for d in state.desk_studies if d.id != study.id)
    return replace(state, desk_studies=tuple(sorted((*others, study), key=lambda d: d.id)))


def _next_id(items: tuple[DeskStudy, ...] | tuple[Project, ...]) -> int:
    return max((x.id for x in items), default=0) + 1


def holder_of(state: GameState, region: str, block: int) -> str | int | None:
    """Who holds a block's licence: a supplier's name, a company id, or None (free)."""
    for s in state.supplier_licences:
        if s.region == region and s.block == block:
            return s.name
    for p in state.projects:
        if p.region == region and p.block == block and p.status in ("active", "permitted"):
            return p.company_id
    return None


def _owned(state: GameState, actor_id: int, project_id: int, balance: Balance) -> Project:
    project = project_of(state, project_id)
    _company(state, actor_id, project.company_id, balance)
    if not project.is_open:
        raise ExplorationRuleError(f"the project is {project.status}")
    return project


def _region_cost(data: GameData, region: str) -> float:
    assert data.geology is not None
    return data.geology.regions[region].cost_index


def hole_cost_cents(project: Project, block: GeoBlock, balance: Balance, data: GameData) -> int:
    db = balance.exploration.drill
    base = db.hole_base_cents + db.hole_per_m_cents * block.depth_m
    return round(base * _region_cost(data, project.region))


def hole_cost_range_cents(region: str, balance: Balance, data: GameData) -> tuple[int, int]:
    """What a hole may cost in a region before any is drilled (the depth is unknown, 34.5)."""
    db = balance.exploration.drill
    lo, hi = balance.geology.depth_m
    index = _region_cost(data, region)
    return (
        round((db.hole_base_cents + db.hole_per_m_cents * lo) * index),
        round((db.hole_base_cents + db.hole_per_m_cents * hi) * index),
    )


def stage_cost_cents(
    project: Project, stage: str, balance: Balance, data: GameData
) -> tuple[int, int]:
    """A stage's cost and months (34.2)."""
    eb = balance.exploration
    if stage == "survey":
        cost = round(eb.survey.cost_cents * _region_cost(data, project.region))
        return cost, eb.survey.months
    if stage == "sampling":
        return eb.sampling.cost_cents, eb.sampling.months
    if stage == "estimate":
        return eb.estimate.cost_cents, eb.estimate.months
    if stage in LEVELS:
        return eb.feasibility.cost_cents[stage], eb.feasibility.months[stage]
    if stage == "permitting":
        return 0, 0
    raise ExplorationRuleError(f"unknown stage {stage!r}")


def start_desk_study(
    state: GameState,
    action: StartDeskStudy,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    company = _company(state, action.actor_id, action.company_id, balance)
    _region(data, action.region)
    c = _commodity(data, action.commodity)
    _need_geologist(state, company.id, balance)
    eb = balance.exploration
    entries = _pay(
        state, company.id, eb.desk.cost_cents, f"Desk study: {c.label}, {action.region}", balances
    )
    state = _energy(state, action.actor_id, action.kind, balance, eb.energy)
    study = DeskStudy(
        id=_next_id(state.desk_studies),
        company_id=company.id,
        region=action.region,
        commodity=c.key,
        start_turn=state.turn,
        done_turn=state.turn + eb.desk.months - 1,
        factor=reading_factor(state, company.id, balance),
    )
    return Outcome(with_study(state, study), entries)


def take_licence(
    state: GameState,
    action: TakeLicence,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    company = _company(state, action.actor_id, action.company_id, balance)
    _region(data, action.region)
    if not 0 <= action.block < balance.geology.blocks_per_region:
        raise ExplorationRuleError(f"no block {action.block} in {action.region}")
    if holder_of(state, action.region, action.block) is not None:
        raise ExplorationRuleError("that block is already licensed")
    assert data.geology is not None
    fee = data.geology.regions[action.region].licence_fee_cents
    entries = _pay(
        state, company.id, fee, f"Exploration licence: {action.region} {action.block}", balances
    )
    state = _energy(state, action.actor_id, action.kind, balance, balance.exploration.energy)
    years = balance.exploration.licence.years
    project = Project(
        id=_next_id(state.projects),
        company_id=company.id,
        region=action.region,
        block=action.block,
        licence_turn=state.turn,
        expires_turn=state.turn + years * MONTHS_A_YEAR,
        spent_cents=fee,
    )
    log = inbox_item(
        state.turn,
        company.id,
        "licence_taken",
        link_kind=LINK,
        link_id=project.id,
        block=label_of(project),
        fee=format_money(fee),
    )
    return Outcome(with_project(state, project), entries, (log,))


def renew_licence(
    state: GameState,
    action: RenewLicence,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    project = _owned(state, action.actor_id, action.project_id, balance)
    if project.renewals >= balance.exploration.licence.renewals:
        raise ExplorationRuleError("the licence has been renewed already")
    assert data.geology is not None
    fee = data.geology.regions[project.region].licence_fee_cents
    entries = _pay(
        state, project.company_id, fee, f"Licence renewed: {label_of(project)}", balances
    )
    years = balance.exploration.licence.years
    project = replace(
        project,
        renewals=project.renewals + 1,
        expires_turn=project.expires_turn + years * MONTHS_A_YEAR,
        spent_cents=project.spent_cents + fee,
    )
    return Outcome(with_project(state, project), entries)


def _stage_problem(state: GameState, project: Project, stage: str, balance: Balance) -> str | None:
    """Why a stage cannot start now, in public words (None: it can)."""
    eb = balance.exploration
    if project.stage is not None:
        return f"the {project.stage.replace('_', ' ')} is still running"
    if project.holes_left:
        return "a drilling programme is still running"
    if stage == "survey":
        return None
    if stage == "sampling":
        return None
    if stage == "estimate":
        holes = sum(1 for h in state.holes if h.project_id == project.id)
        if holes < eb.estimate.inferred:
            return f"a resource estimate needs {eb.estimate.inferred} holes ({holes} drilled)"
        return None
    if stage in LEVELS:
        need = eb.feasibility.min_category[stage]
        have = project.category
        if have is None or CATEGORIES.index(have) < CATEGORIES.index(need):
            return f"a {stage.replace('_', '-')} study needs a {need} resource"
        return None
    if stage == "permitting":
        req = eb.permitting.requires
        if project.level is None or LEVELS.index(project.level) < LEVELS.index(req):
            return f"a permit application needs a {req} feasibility study"
        if project.permit_start is not None:
            return "the permit has been applied for"
        return None
    return f"unknown stage {stage!r}"


def start_stage(
    state: GameState,
    action: StartStage,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    project = _owned(state, action.actor_id, action.project_id, balance)
    if problem := _stage_problem(state, project, action.stage, balance):
        raise ExplorationRuleError(problem)
    commodity = project.commodity
    if action.stage == "sampling":
        commodity = action.commodity or project.commodity
        if commodity is None:
            raise ExplorationRuleError("name the commodity to sample for (no anomaly read one)")
        _commodity(data, commodity)
    elif action.commodity is not None and action.commodity != project.commodity:
        raise ExplorationRuleError("only sampling chooses the commodity")
    if action.stage in ("estimate", *LEVELS) and commodity is None:
        raise ExplorationRuleError("sample the block for a commodity first")
    if action.stage in GEOLOGY_STAGES:
        _need_geologist(state, project.company_id, balance)
    cost, months = stage_cost_cents(project, action.stage, balance, data)
    words = action.stage.replace("_", "-") if action.stage in LEVELS else action.stage
    entries = _pay(
        state, project.company_id, cost, f"Exploration {words}: {label_of(project)}", balances
    )
    state = _energy(state, action.actor_id, action.kind, balance, balance.exploration.energy)
    project = replace(
        project,
        commodity=commodity,
        stage=action.stage,
        stage_start=state.turn,
        stage_due=state.turn + months - 1 if months else None,
        spent_cents=project.spent_cents + cost,
    )
    if action.stage == "permitting":
        project = _apply_permit(state, project, rng, balance, data)
    return Outcome(with_project(state, project), entries)


def order_drilling(
    state: GameState, action: OrderDrilling, balance: Balance, data: GameData
) -> Outcome:
    """A programme of holes (34.2), drilled holes_per_month at a time and paid hole by hole."""
    project = _owned(state, action.actor_id, action.project_id, balance)
    db = balance.exploration.drill
    if not 1 <= action.holes <= db.max_programme:
        raise ExplorationRuleError(f"a programme is 1-{db.max_programme} holes")
    if problem := _stage_problem(state, project, "survey", balance):
        raise ExplorationRuleError(problem)
    if project.commodity is None:
        raise ExplorationRuleError("sample the block for a commodity before drilling")
    _need_geologist(state, project.company_id, balance)
    state = _energy(state, action.actor_id, action.kind, balance, balance.exploration.energy)
    project = replace(project, holes_left=action.holes, stage="drilling", stage_start=state.turn)
    return Outcome(with_project(state, project))


def relinquish(state: GameState, action: RelinquishProject, balance: Balance) -> Outcome:
    project = _owned(state, action.actor_id, action.project_id, balance)
    project = replace(
        project, status="relinquished", stage=None, holes_left=0, ended_turn=state.turn
    )
    return Outcome(with_project(state, project))


# --- What a project would fetch (34.2) --------------------------------------------------------


def sale_stage(state: GameState, project: Project) -> str | None:
    """The furthest stage reached, for the sale share."""
    if project.status == "permitted":
        return "permitted"
    if project.level is not None:
        return project.level
    if project.category is not None:
        return "estimated"
    if any(h.project_id == project.id for h in state.holes):
        return "drilled"
    if project.sample_center is not None:
        return "sampled"
    if project.reading is not None:
        return "surveyed"
    return None


def indicative_npv_cents(
    state: GameState, project: Project, balance: Balance, data: GameData
) -> int | None:
    """What a buyer counts on (34.2): the NPV at the price deck at the low end of what has
    been revealed: the latest study's low end, else the estimate's or the sample's low grade
    and tonnage with the commodity's typical costs (the typical depth and distance to
    infrastructure, never the block's own). Narrower ranges fetch more."""
    if project.npv_lo_cents is not None:
        return project.npv_lo_cents
    if project.commodity is None or data.geology is None:
        return None
    c = data.geology.commodity(project.commodity)
    est = running_estimate(state, project, balance, data)
    if project.est_grade_center is not None and project.est_tonnage_center is not None:
        assert project.est_grade_hw is not None and project.est_tonnage_hw is not None
        grade = math.exp(project.est_grade_center - project.est_grade_hw)
        tonnage = math.exp(project.est_tonnage_center - project.est_tonnage_hw)
    elif est is not None:
        grade, tonnage = math.exp(est[0] - est[1]), c.tonnage_median_mt
    elif project.sample_center is not None and project.sample_hw is not None:
        grade, tonnage = math.exp(project.sample_center - project.sample_hw), c.tonnage_median_mt
    else:
        return None
    depth = sum(balance.geology.depth_m) / 2  # typical: never the block's own (34.5)
    infra = math.sqrt(balance.geology.infra_km[0] * balance.geology.infra_km[1])
    kind = project.kind or next(iter(data.geology.kinds_of(project.region, c.key)))
    rec = c.recovery[0]
    usd = mine_npv_usd(state, c, tonnage, grade, rec, kind, infra, depth, 1.0, 1.0, balance, data)
    return round(usd * 100)


def mine_npv_usd(
    state: GameState,
    c: GeoCommodity,
    tonnage: float,
    grade: float,
    recovery: float,
    kind: str,
    infra_km: float,
    depth_m: float,
    capex_mult: float,
    opex_mult: float,
    balance: Balance,
    data: GameData,
) -> float:
    """34.2: NPV at the price deck. Capex and operating cost scale with ore moved: the
    commodity's intensities hold at its median grade and mid recovery."""
    fb = balance.exploration.feasibility
    d = deck(state, c.key, data, balance)
    ref = c.grade_median * sum(c.recovery) / 2  # product per tonne of ore at the reference
    product = grade * recovery
    capex = (
        xf.capex_usd(
            tonnage_mt=tonnage,
            grade=ref,
            recovery=1.0,
            intensity=c.capex_per_tpy_usd,
            kind_mult=fb.kind_capex[kind],
            infra_km=infra_km,
            depth_m=depth_m,
            fb=fb,
        )
        * capex_mult
    )
    opex_per_t = c.opex_per_t_usd * fb.kind_opex[kind] * ref / product * opex_mult
    return xf.npv_usd(
        tonnage_mt=tonnage,
        grade=grade,
        recovery=recovery,
        capex_usd=capex,
        opex_per_t=opex_per_t,
        price_now=usd_per_tonne(d, "current"),
        price_long=usd_per_tonne(d, "long_run"),
        build_years=fb.build_years[kind],
        fb=fb,
    )


def sale_price_cents(state: GameState, project: Project, balance: Balance, data: GameData) -> int:
    sb = balance.exploration.sale
    stage = sale_stage(state, project)
    if stage is None:
        return 0
    npv = indicative_npv_cents(state, project, balance, data)
    share = sb.share.get(stage, 0.0)
    price = round(share * max(0, npv or 0))
    if project.reading == "strong" and stage == "surveyed":
        price = max(price, sb.anomaly_cents)
    return price


def buyer_for(project: Project, data: GameData) -> tuple[str, str] | None:
    """The supplier that buys a project: the first of the commodity's buyers headquartered in
    its region, else the first (from public facts only: the commodity and the region)."""
    if project.commodity is None:
        return None
    buyers = buyers_of(data, project.commodity)
    if not buyers:
        return None
    local = [b for b in buyers if b.region == project.region]
    b = (local or list(buyers))[0]
    return b.key, b.name


def sell_project(
    state: GameState, action: SellProject, balance: Balance, data: GameData
) -> Outcome:
    project = project_of(state, action.project_id)
    _company(state, action.actor_id, project.company_id, balance)
    if project.status not in ("active", "permitted"):
        raise ExplorationRuleError(f"the project is {project.status}")
    price = sale_price_cents(state, project, balance, data)
    buyer = buyer_for(project, data)
    if price <= 0 or buyer is None:
        raise ExplorationRuleError("no supplier would pay for the project at this stage")
    state = _energy(state, action.actor_id, action.kind, balance, balance.exploration.sale.energy)
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=project.company_id,
        memo=f"Exploration project sold to {buyer[1]}: {label_of(project)}",
        debit=CASH,
        credit=DISPOSAL,
        amount=price,
    )
    project = replace(
        project,
        status="sold",
        stage=None,
        holes_left=0,
        sold_to=buyer[1],
        sale_cents=price,
        ended_turn=state.turn,
    )
    state = with_project(state, project)
    licences = tuple(
        sorted(
            (*state.supplier_licences, SupplierLicence(project.region, project.block, *buyer)),
            key=lambda x: (x.region, x.block),
        )
    )
    state = replace(state, supplier_licences=licences)
    log = inbox_item(
        state.turn,
        project.company_id,
        "project_sold",
        link_kind=LINK,
        link_id=project.id,
        block=label_of(project),
        buyer=buyer[1],
        price=format_money(price),
    )
    return Outcome(state, (entry,), (log,))


def apply_exploration(
    state: GameState,
    action: ExplorationAction,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    match action:
        case StartDeskStudy():
            return start_desk_study(state, action, balances, balance, data)
        case TakeLicence():
            return take_licence(state, action, balances, balance, data)
        case RenewLicence():
            return renew_licence(state, action, balances, balance, data)
        case StartStage():
            return start_stage(state, action, rng, balances, balance, data)
        case OrderDrilling():
            return order_drilling(state, action, balance, data)
        case SellProject():
            return sell_project(state, action, balance, data)
        case RelinquishProject():
            return relinquish(state, action, balance)


def label_of(project: Project) -> str:
    return f"{project.region.replace('_', ' ').title()} block {project.block + 1}"


# --- Stage results (the monthly phase) ---------------------------------------------------------


def _truth(state: GameState, project: Project, data: GameData) -> tuple[GeoBlock, bool]:
    block = block_of(state, project.region, project.block)
    if block is None:
        raise ExplorationRuleError("no geology for this block (a save from before M18)")
    return block, project.commodity is not None and block.true_commodity == project.commodity


def _grade_truth(block: GeoBlock, hit: bool, c: GeoCommodity) -> float:
    return block.true_grade if hit else c.trace_grade


def _tonnage_truth(block: GeoBlock, hit: bool, c: GeoCommodity) -> float:
    return block.true_tonnage_mt if hit else c.tonnage_median_mt * TRACE_TONNAGE


def desk_bands(
    state: GameState, study: DeskStudy, rng: RngFactory, balance: Balance
) -> tuple[str, ...]:
    """34.2: each block's latent score is the signal if it holds the commodity, plus noise x
    the team's range factor; the top high_share of the region's blocks show high, the next
    medium_share medium, the rest low."""
    db = balance.exploration.desk
    blocks = sorted(
        (b for b in state.geo_blocks if b.region == study.region), key=lambda b: b.index
    )
    z = rng.stream(study.done_turn, "exploration", DESK, study.id).standard_normal(len(blocks))
    scores = [
        (db.signal if b.true_commodity == study.commodity else 0.0)
        + db.noise_sd * study.factor * float(z[i])
        for i, b in enumerate(blocks)
    ]
    order = sorted(range(len(blocks)), key=lambda i: (-scores[i], i))
    n = len(blocks)
    high, medium = round(db.high_share * n), round(db.medium_share * n)
    bands = ["low"] * n
    for rank, i in enumerate(order):
        bands[i] = "high" if rank < high else "medium" if rank < high + medium else "low"
    return tuple(bands)


def survey_result(
    state: GameState, project: Project, rng: RngFactory, balance: Balance, data: GameData
) -> Project:
    """34.2: an anomaly reading (none, weak, strong) and, with one, its commodity and type."""
    assert data.geology is not None
    sb = balance.exploration.survey
    block = block_of(state, project.region, project.block)
    assert block is not None
    field = reading_factor(state, project.company_id, balance)
    gen = rng.stream(state.turn, "exploration", SURVEY, project.id)
    z = float(gen.standard_normal())
    u_mis, u_c, u_kind = (float(x) for x in gen.random(3))
    value = sb.noise_sd * field * z
    if block.true_commodity is not None:
        c = data.geology.commodity(block.true_commodity)
        size = (block.true_tonnage_mt / c.tonnage_median_mt) ** sb.size_weight
        value += sb.signal * size
    reading = "strong" if value >= sb.strong_at else "weak" if value >= sb.weak_at else "none"
    commodity, kind = project.commodity, None
    if reading != "none":
        weights = data.geology.regions[project.region].prospectivity
        if block.true_commodity is not None and u_mis >= sb.commodity_misread * field:
            commodity = block.true_commodity
        else:
            commodity = _weighted(weights, u_c)
        kind = (
            block.true_kind
            if commodity == block.true_commodity
            else _weighted(data.geology.kinds_of(project.region, commodity), u_kind)
        )
    return replace(project, reading=reading, commodity=commodity, kind=kind)


def _weighted(weights: dict[str, float], u: float) -> str:
    total = sum(weights.values())
    acc = 0.0
    for key, w in weights.items():
        acc += w / total
        if u < acc:
            return key
    return next(reversed(weights))


def sample_result(
    state: GameState, project: Project, rng: RngFactory, balance: Balance, data: GameData
) -> Project:
    """34.2: a first grade range, +/-60% at a range factor of 1 (as shown: sinh of the log
    half-width), centred on the truth plus noise of the same stated confidence."""
    assert data.geology is not None and project.commodity is not None
    eb = balance.exploration
    block, hit = _truth(state, project, data)
    c = data.geology.commodity(project.commodity)
    field, _ = factors(state, project.company_id, balance)
    hw = math.asinh(eb.sampling.range) * field
    sd = hw / xf.z_of(eb.confidence)
    z = float(rng.stream(state.turn, "exploration", SAMPLE, project.id).standard_normal())
    center = math.log(_grade_truth(block, hit, c)) + sd * z
    kind = project.kind or (
        block.true_kind if hit else next(iter(data.geology.kinds_of(project.region, c.key)))
    )
    return replace(project, sample_center=center, sample_hw=hw, kind=kind)


def drill_hole(
    state: GameState,
    project: Project,
    n: int,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> Hole:
    """34.2: hole n samples the ore body's position perm[n] (not yet drilled); its assay is the
    deposit's grade x exp(range factor x hole_sd x that position's deviation). Where the block
    holds none of the commodity, background mineralisation with the same spread."""
    assert data.geology is not None and project.commodity is not None
    block, hit = _truth(state, project, data)
    c = data.geology.commodity(project.commodity)
    field, _ = factors(state, project.company_id, balance)
    r = data.region_keys.index(project.region)
    cells = balance.geology.cells
    if hit:
        devs = cell_deviations(rng, r, project.block, cells)
        perm = rng.stream(GEOLOGY_TURN, "geology", r, project.block, PERM_TAG).permutation(cells)
        dev = devs[int(perm[(n - 1) % cells])]
    else:
        dev = float(
            rng.stream(state.turn, "exploration", HOLE, r, project.block, n).standard_normal()
        )
    assay = math.exp(math.log(_grade_truth(block, hit, c)) + field * c.hole_sd * dev)
    return Hole(
        project_id=project.id,
        n=n,
        turn=state.turn,
        assay=assay,
        factor=field,
        cost_cents=hole_cost_cents(project, block, balance, data),
    )


def holes_of(state: GameState, project_id: int) -> tuple[Hole, ...]:
    return tuple(h for h in state.holes if h.project_id == project_id)


def running_estimate(
    state: GameState, project: Project, balance: Balance, data: GameData
) -> tuple[float, float] | None:
    """The running grade estimate (log centre, half-width) from the holes alone (34.2)."""
    holes = holes_of(state, project.id)
    if not holes or project.commodity is None or data.geology is None:
        return None
    c = data.geology.commodity(project.commodity)
    return xf.grade_estimate(
        [h.assay for h in holes],
        [h.factor for h in holes],
        c.hole_sd,
        balance.geology.cells,
        balance.exploration.confidence,
    )


def estimate_result(
    state: GameState, project: Project, rng: RngFactory, balance: Balance, data: GameData
) -> Project:
    """34.2: a resource in its category with grade (from the holes) and tonnage ranges."""
    assert data.geology is not None and project.commodity is not None
    eb = balance.exploration
    block, hit = _truth(state, project, data)
    c = data.geology.commodity(project.commodity)
    holes = holes_of(state, project.id)
    category = xf.category_for(
        len(holes), eb.estimate.inferred, eb.estimate.indicated, eb.estimate.measured
    )
    grade = running_estimate(state, project, balance, data)
    if category is None or grade is None:
        return project
    _, est = factors(state, project.company_id, balance)
    sd = eb.estimate.tonnage_sd[category] * est
    z = float(rng.stream(state.turn, "exploration", ESTIMATE, project.id).standard_normal())
    return replace(
        project,
        category=category,
        est_holes=len(holes),
        est_grade_center=grade[0],
        est_grade_hw=grade[1],
        est_tonnage_center=math.log(_tonnage_truth(block, hit, c)) + sd * z,
        est_tonnage_hw=xf.z_of(eb.confidence) * sd,
        est_turn=state.turn,
    )


def study_result(
    state: GameState,
    project: Project,
    level: str,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> Project:
    """34.2: capex, operating cost and recovery ranges, each centred on the truth plus noise
    of the level's accuracy x the team's range factor; then an NPV range at the price deck from
    the low and high ends of every range, and its midpoint from their centres."""
    assert data.geology is not None and project.commodity is not None
    eb = balance.exploration
    fb = eb.feasibility
    block, hit = _truth(state, project, data)
    c = data.geology.commodity(project.commodity)
    kind = project.kind or next(iter(data.geology.kinds_of(project.region, c.key)))
    _, est = factors(state, project.company_id, balance)
    z90 = xf.z_of(eb.confidence)
    gen = rng.stream(state.turn, "exploration", STUDY, project.id, LEVELS.index(level))
    z_cap, z_op, z_rec = (float(x) for x in gen.standard_normal(3))
    a, r_sd = fb.accuracy[level] * est, fb.recovery_sd[level] * est
    rec_true = block.true_recovery if hit else sum(c.recovery) / 2
    tonnage, grade = _tonnage_truth(block, hit, c), _grade_truth(block, hit, c)
    true_capex = _capex(c, tonnage, kind, block.true_infra_km, block.depth_m, fb)
    ref = c.grade_median * sum(c.recovery) / 2
    true_opex = c.opex_per_t_usd * fb.kind_opex[kind] * ref / (grade * rec_true)
    capex_c, opex_c = math.log(true_capex) + a * z_cap, math.log(true_opex) + a * z_op
    rec_c = min(0.99, max(0.05, rec_true + r_sd * z_rec))
    rec_hw = z90 * r_sd
    assert project.est_grade_center is not None and project.est_grade_hw is not None
    assert project.est_tonnage_center is not None and project.est_tonnage_hw is not None
    g_c, g_hw = project.est_grade_center, project.est_grade_hw
    t_c, t_hw = project.est_tonnage_center, project.est_tonnage_hw
    cap_hw = op_hw = z90 * a

    def npv(sign: int) -> int:
        t = math.exp(t_c + sign * t_hw)
        g = math.exp(g_c + sign * g_hw)
        rec = min(0.99, max(0.05, rec_c + sign * rec_hw))
        capex = math.exp(capex_c - sign * cap_hw) * t / math.exp(t_c)  # capex scales with ore
        opex_t = math.exp(opex_c - sign * op_hw) * (math.exp(g_c) * rec_c) / (g * rec)
        return round(_npv_with(state, c, t, g, rec, capex, opex_t, kind, balance, data) * 100)

    return replace(
        project,
        kind=kind,
        level=level,
        capex_center=capex_c,
        capex_hw=cap_hw,
        opex_center=opex_c,
        opex_hw=op_hw,
        recovery_center=rec_c,
        recovery_hw=rec_hw,
        npv_lo_cents=npv(-1),
        npv_mid_cents=npv(0),
        npv_hi_cents=npv(1),
        study_turn=state.turn,
    )


def _capex(
    c: GeoCommodity, tonnage: float, kind: str, infra_km: float, depth_m: float, fb: object
) -> float:
    from tst.sim.exploration.config import FeasibilityBalance

    assert isinstance(fb, FeasibilityBalance)
    ref = c.grade_median * sum(c.recovery) / 2
    return xf.capex_usd(
        tonnage_mt=tonnage,
        grade=ref,
        recovery=1.0,
        intensity=c.capex_per_tpy_usd,
        kind_mult=fb.kind_capex[kind],
        infra_km=infra_km,
        depth_m=depth_m,
        fb=fb,
    )


def _npv_with(
    state: GameState,
    c: GeoCommodity,
    tonnage: float,
    grade: float,
    recovery: float,
    capex: float,
    opex_t: float,
    kind: str,
    balance: Balance,
    data: GameData,
) -> float:
    fb = balance.exploration.feasibility
    d = deck(state, c.key, data, balance)
    return xf.npv_usd(
        tonnage_mt=tonnage,
        grade=grade,
        recovery=recovery,
        capex_usd=capex,
        opex_per_t=opex_t,
        price_now=usd_per_tonne(d, "current"),
        price_long=usd_per_tonne(d, "long_run"),
        build_years=fb.build_years[kind],
        fb=fb,
    )


def true_npv_usd(state: GameState, block: GeoBlock, balance: Balance, data: GameData) -> float:
    """A deposit's NPV at the price deck from its hidden truth (the balance runner's
    "feasible" deposits; never shown)."""
    assert data.geology is not None and block.true_commodity is not None
    c = data.geology.commodity(block.true_commodity)
    fb = balance.exploration.feasibility
    kind = block.true_kind or "hard_rock"
    capex = _capex(c, block.true_tonnage_mt, kind, block.true_infra_km, block.depth_m, fb)
    ref = c.grade_median * sum(c.recovery) / 2
    opex_t = c.opex_per_t_usd * fb.kind_opex[kind] * ref / (block.true_grade * block.true_recovery)
    return _npv_with(
        state,
        c,
        block.true_tonnage_mt,
        block.true_grade,
        block.true_recovery,
        capex,
        opex_t,
        kind,
        balance,
        data,
    )


def _apply_permit(
    state: GameState, project: Project, rng: RngFactory, balance: Balance, data: GameData
) -> Project:
    """34.2: the permit's decision month, from the region's years x the block's hidden
    difficulty (and the deposit type: brine slower), drawn now and never shown."""
    assert data.geology is not None
    lo, hi = data.geology.regions[project.region].permit_years
    block = block_of(state, project.region, project.block)
    assert block is not None
    u = float(rng.stream(state.turn, "exploration", PERMIT, project.id).random())
    years = (lo + (hi - lo) * u) * block.true_difficulty
    months = max(MIN_PERMIT_MONTHS, round(years * MONTHS_A_YEAR))
    return replace(project, permit_start=state.turn, hidden_due_turn=state.turn + months - 1)


def permit_range_years(region: str, data: GameData) -> tuple[float, float]:
    """What the player is told: the region's typical years (34.5), never the drawn month."""
    assert data.geology is not None
    return data.geology.regions[region].permit_years
