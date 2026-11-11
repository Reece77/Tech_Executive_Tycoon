"""The Exploration screen's read model (M18, formulas.md 34.5). Every number here comes from
what has been revealed: desk-study bands, survey readings, assays, the stored estimate and study
results, and public region data. Nothing reads a block's true_* fields or a project's hidden
permit month, so two blocks with the same revealed results look the same (the differential
test in tests/integration/test_api_exploration.py)."""

from __future__ import annotations

import math

from tst.api import howto
from tst.api.schemas.exploration import (
    DeskStudyOut,
    DrillHoleOut,
    EstimateRangeOut,
    ExplorationOut,
    ExplorationProjectOut,
    ExplorerOut,
    GeoBlockOut,
    GeoCommodityOut,
    GeoRegionOut,
    StageOptionOut,
)
from tst.loader import LoadedData
from tst.sim.exploration import pipeline as xp
from tst.sim.exploration.config import LEVELS
from tst.sim.exploration.formulas import half_width_pct
from tst.sim.exploration.models import Project
from tst.sim.ledger import LedgerBalances
from tst.sim.state import GameState

STAGE_ORDER = ("survey", "sampling", "drilling", "estimate", *LEVELS, "permitting")


def _range(center: float | None, hw: float | None) -> EstimateRangeOut | None:
    if center is None or hw is None:
        return None
    return EstimateRangeOut(
        low=math.exp(center - hw),
        mid=math.exp(center),
        high=math.exp(center + hw),
        pct=half_width_pct(hw),
    )


def _linear(center: float | None, hw: float | None) -> EstimateRangeOut | None:
    if center is None or hw is None:
        return None
    return EstimateRangeOut(
        low=center - hw, mid=center, high=center + hw, pct=hw / center if center else 0
    )


def _options(state: GameState, project: Project, data: LoadedData) -> list[StageOptionOut]:
    b, d = data.balance, data.game_data
    out = []
    for stage in STAGE_ORDER:
        if stage == "drilling":
            lo, _ = xp.hole_cost_range_cents(project.region, b, d)
            problem = xp._stage_problem(state, project, "survey", b)
            if problem is None and project.commodity is None:
                problem = "sample the block for a commodity first"
            out.append(
                StageOptionOut(
                    stage=stage,
                    cost_cents=lo,
                    months=0,
                    allowed=problem is None,
                    reason=problem or "",
                    how=howto.exploration_how(state, project, stage, problem or "", data),
                )
            )
            continue
        cost, months = xp.stage_cost_cents(project, stage, b, d)
        problem = xp._stage_problem(state, project, stage, b)
        if problem is None and stage in ("estimate", *LEVELS) and project.commodity is None:
            problem = "sample the block for a commodity first"
        reason = problem or ("" if project.is_open else f"the project is {project.status}")
        out.append(
            StageOptionOut(
                stage=stage,
                cost_cents=cost,
                months=months,
                allowed=project.is_open and problem is None,
                reason=reason,
                how=howto.exploration_how(state, project, stage, reason, data),
            )
        )
    return out


def _next_step(project: Project, options: list[StageOptionOut]) -> str:
    """What to do next on the project (M23c): the furthest stage allowed now, else the way to
    the first greyed-out one."""
    if not project.is_open:
        return ""
    allowed = [o for o in options if o.allowed]
    if project.stage is None and not project.holes_left and allowed:
        best = allowed[-1]
        return f"next: {best.stage.replace('_', ' ')} is open"
    blocked = next((o for o in options if not o.allowed and o.how), None)
    return f"next: {blocked.how}" if blocked else ""


def _renew_how(project: Project, renewals: int) -> str:
    if project.is_open and project.renewals < renewals:
        return ""
    if not project.is_open:
        return f"none: the project is {project.status}"
    return f"none: a licence renews {renewals} time{'s' if renewals != 1 else ''}; sell or build"


def project_out(state: GameState, project: Project, data: LoadedData) -> ExplorationProjectOut:
    b, d = data.balance, data.game_data
    sb = b.exploration.survey
    est = xp.running_estimate(state, project, b, d)
    chance = sb.bands.get(project.reading) if project.reading else None
    buyer = xp.buyer_for(project, d, state.turn)
    quote = (
        xp.sale_price_cents(state, project, b, d)
        if project.status in ("active", "permitted")
        else 0
    )
    years = xp.permit_range_years(project.region, d) if project.permit_start is not None else None
    options = _options(state, project, data)
    nxt = howto.next_category(project)
    return ExplorationProjectOut(
        id=project.id,
        company_id=project.company_id,
        company=state.company(project.company_id).name,
        region=project.region,
        block=project.block,
        label=xp.label_of(project),
        status=project.status,
        commodity=project.commodity,
        stage=project.stage,
        stage_due_turn=project.stage_due,
        holes_left=project.holes_left,
        licence_turn=project.licence_turn,
        expires_turn=project.expires_turn,
        renewals=project.renewals,
        renewable=project.is_open and project.renewals < b.exploration.licence.renewals,
        spent_cents=project.spent_cents,
        reading=project.reading,
        deposit_chance_low=chance[0] if chance else None,
        deposit_chance_high=chance[1] if chance else None,
        kind=project.kind,
        sample_grade=_range(project.sample_center, project.sample_hw),
        holes=[
            DrillHoleOut(n=h.n, turn=h.turn, assay=h.assay, cost_cents=h.cost_cents)
            for h in xp.holes_of(state, project.id)
        ],
        grade=_range(*est) if est else None,
        category=project.category,
        est_grade=_range(project.est_grade_center, project.est_grade_hw),
        est_tonnage_mt=_range(project.est_tonnage_center, project.est_tonnage_hw),
        level=project.level,
        capex_usd=_range(project.capex_center, project.capex_hw),
        opex_usd_per_t=_range(project.opex_center, project.opex_hw),
        recovery=_linear(project.recovery_center, project.recovery_hw),
        npv_low_cents=project.npv_lo_cents,
        npv_mid_cents=project.npv_mid_cents,
        npv_high_cents=project.npv_hi_cents,
        permit_start=project.permit_start,
        permit_years_low=years[0] if years else None,
        permit_years_high=years[1] if years else None,
        protests=project.protests,
        protest_open=project.protest_turn is not None,
        benefit_agreement=project.benefit,
        pushes=project.pushes,
        permit_turn=project.permit_turn,
        sale_quote_cents=quote if buyer else 0,
        buyer=buyer[1] if buyer else None,
        sold_to=project.sold_to,
        sale_cents=project.sale_cents,
        options=options,
        holes_drilled=howto.holes_drilled(state, project),
        next_category=nxt,
        holes_for_next=howto.holes_for(nxt, data) if nxt else None,
        next_step=_next_step(project, options),
        renew_how=_renew_how(project, b.exploration.licence.renewals),
    )


def exploration_out(state: GameState, balances: LedgerBalances, data: LoadedData) -> ExplorationOut:
    b, d = data.balance, data.game_data
    geo = d.geology
    assert geo is not None
    eb = b.exploration
    explorers = xp.explorers(state)
    ids = {c.id for c in explorers}
    regions = [
        GeoRegionOut(
            key=key,
            label=d.region(key).label,
            prospectivity=dict(geo.regions[key].prospectivity),
            basis=dict(geo.regions[key].basis),
            licence_fee_cents=geo.regions[key].licence_fee_cents,
            permit_years_low=geo.regions[key].permit_years[0],
            permit_years_high=geo.regions[key].permit_years[1],
            survey_cost_cents=round(eb.survey.cost_cents * geo.regions[key].cost_index),
            hole_cost_low_cents=xp.hole_cost_range_cents(key, b, d)[0],
            hole_cost_high_cents=xp.hole_cost_range_cents(key, b, d)[1],
        )
        for key in d.region_keys
    ]
    latest: dict[tuple[str, str], tuple[str, ...]] = {}
    for study in sorted(state.desk_studies, key=lambda s: s.id):
        if study.company_id in ids and study.done:
            latest[(study.region, study.commodity)] = study.bands
    open_projects = {
        (p.region, p.block): p.id
        for p in state.projects
        if p.company_id in ids and p.status in ("active", "permitted")
    }
    blocks = []
    for region in d.region_keys:
        for i in range(b.geology.blocks_per_region):
            holder = xp.holder_of(state, region, i)
            blocks.append(
                GeoBlockOut(
                    region=region,
                    index=i,
                    holder=state.company(holder).name if isinstance(holder, int) else holder,
                    project_id=open_projects.get((region, i)),
                    bands={c: bands[i] for (r, c), bands in latest.items() if r == region},
                )
            )
    return ExplorationOut(
        turn=state.turn,
        confidence=eb.confidence,
        desk_cost_cents=eb.desk.cost_cents,
        desk_months=eb.desk.months,
        max_programme=eb.drill.max_programme,
        licence_years=eb.licence.years,
        licence_renewals=eb.licence.renewals,
        gate_how=howto.stage_how(
            eb.min_stage, max((c.stage for c in explorers), default=0), "exploration"
        ),
        commodities=[
            GeoCommodityOut(key=c.key, label=c.label, grade_unit=c.grade_unit)
            for c in geo.commodities
        ],
        regions=regions,
        explorers=[
            ExplorerOut(
                company_id=c.id,
                name=c.name,
                geologists=len(xp.geologists(state, c.id, b)),
                busy=xp.busy_count(state, c.id),
                gate=xp.gate(state, c, b),
            )
            for c in explorers
        ],
        blocks=blocks,
        desk_studies=[
            DeskStudyOut(
                id=s.id,
                company_id=s.company_id,
                region=s.region,
                commodity=s.commodity,
                start_turn=s.start_turn,
                done_turn=s.done_turn,
                done=s.done,
            )
            for s in state.desk_studies
            if s.company_id in ids
        ],
        projects=[project_out(state, p, data) for p in state.projects if p.company_id in ids],
    )
