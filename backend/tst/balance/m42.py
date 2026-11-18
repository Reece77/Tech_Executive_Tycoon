"""M42's balance targets (docs/formulas.md 55.6), printed by tools/m42_targets.py.

1. History holds: unit tests (tests/unit/test_m42_pharma.py), golden snapshots and M28's history
   fingerprint; a company without pharma plays exactly as before.
2. Attrition is real: of a cohort of programmes entering Phase I (`COHORT_PER_AREA` in each area,
   January 2021, the standard design), the share reaching US approval is 6-12% (median over
   seeds), with oncology at least 30% below the average. Measured on the engine's own stage,
   readout, filing and decision steps, played as a sensible company would: each next trial at the
   standard design as soon as the last reads out, a filing with the FDA after Phase III (or after
   Phase II where accelerated approval allows it), a resubmission after a complete response
   letter, and a failed programme stopped.
3. It takes a decade: the median months from Phase I's start to US approval, 7-11 years.
4. The cliff bites: a small-molecule blockbuster (efficacy 0.8, on the market in every region)
   loses at least 70% of its revenue within 24 months of its exclusivity ending: its revenue 24
   months after exclusivity has ended in every region, against the month before it ends in any
   (each region's dates are its own: US, EU, elsewhere).
5. AI helps, modestly: two portfolios from discovery (`AI_COHORT` programmes each, the same
   molecules' draws), one with AI discovery: approvals per dollar of R&D are 10-40% higher with
   AI (median over seeds).
6. Turn time: `make check-timing` (tests/timing).
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from typing import Final

from tst.balance.m28 import SEEDS, loaded
from tst.balance.report import Row, table
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.pharma import approval, demand, draws, pipeline
from tst.sim.pharma import data as pd
from tst.sim.pharma.config import AREAS, Design
from tst.sim.pharma.models import Authorisation, Drug, Hta, Programme
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import GameState

COHORT_PER_AREA: Final = 100
AI_COHORT: Final = 700
START: Final = ym_to_turn(2021, 1)
HORIZON: Final = 30 * 12  # months a cohort is followed
FDA: Final = "fda_drugs"
PLAYER: Final = 1
DESIGN: Final[Design] = "standard"
BLOCKBUSTER_EFFICACY: Final = 0.8


@dataclass(frozen=True, slots=True)
class SeedResult:
    seed: int
    approved: int
    total: int
    oncology_approved: int
    oncology_total: int
    months_to_approval: tuple[int, ...]
    cliff_loss: float
    ai_per_b: float
    plain_per_b: float


_BASES: dict[int, GameState] = {}


def _bare(data: LoadedData, seed: int, turn: int) -> GameState:
    if seed not in _BASES:
        found = data.game_data.scenario("ex_big_tech_founders")
        assert found is not None
        state, _ = new_game(
            save_name="m42",
            master_seed=seed,
            scenario=found,
            difficulty="standard",
            company_name="Pharma Co",
            founder=DEFAULT_FOUNDER,
            balance=data.balance,
            data=data.game_data,
        )
        _BASES[seed] = state
    return replace(_BASES[seed], turn=turn)


def _indications(data: LoadedData) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {a: [] for a in AREAS}
    for ind in pd.file(data.game_data).indications:
        out[ind.area].append(ind.key)
    return out


def _cohort(
    state: GameState, rng: RngFactory, data: LoadedData, stage: str, per_area: int, ai: bool
) -> GameState:
    """Programmes of the player's, `per_area` in each area, starting `stage` this month."""
    b, gd = data.balance, data.game_data
    inds = _indications(data)
    rows: list[Programme] = []
    pid = 0
    for area in AREAS:
        for k in range(per_area):
            pid += 1
            ind = inds[area][k % len(inds[area])]
            eff, saf = pipeline.draw_molecule(
                state.turn, rng, draws.MOLECULE, (pid,), ai=ai, lead=0.0, balance=b
            )
            p = Programme(
                id=pid,
                company_id=PLAYER,
                name=f"P{pid}",
                indication=ind,
                area=area,  # type: ignore[arg-type]
                modality="small_molecule" if pid % 2 else "biologic",
                stage="discovery",
                start_turn=state.turn,
                due_turn=state.turn,
                efficacy=eff,
                safety=saf,
                ai=ai,
                patent_turn=state.turn,
            )
            if stage == "discovery":
                months = pipeline.stage_months(p, "discovery", DESIGN, b, gd)
                p = replace(
                    p,
                    due_turn=state.turn + months,
                    cost_cents=pipeline.stage_cost_cents(p, "discovery", 0, months, b, gd),
                )
            else:
                p = pipeline.begin_stage(state, p, stage, DESIGN, b, gd)
            rows.append(p)
    return replace(state, pharma_programmes=tuple(rows))


def _play(
    state: GameState, rng: RngFactory, data: LoadedData, months: int
) -> tuple[GameState, int]:
    """The engine's pipeline and approval steps month by month, with the sensible policy; the
    R&D spent (game cents)."""
    b, gd = data.balance, data.game_data
    spent = 0
    end = state.turn + months
    while state.turn < end:
        state, entries, _ = pipeline.month(state, rng, b, gd)
        spent += sum(e.lines[0].amount for e in entries if e.company_id == PLAYER)
        state, _, _ = approval.month(state, rng, b, gd)
        for p in list(state.pharma_programmes):
            p = next(q for q in state.pharma_programmes if q.id == p.id)
            if p.status == "failed":
                state = pipeline.with_programme(
                    state, replace(p, status="stopped", ended_turn=state.turn)
                )
            elif p.status == "ready":
                state = _advance(state, p, rng, data)
        if all(p.status in ("stopped", "marketed") for p in state.pharma_programmes):
            break
        state = replace(state, turn=state.turn + 1)
    return state, spent


def _advance(state: GameState, p: Programme, rng: RngFactory, data: LoadedData) -> GameState:
    b, gd = data.balance, data.game_data
    reviews = [r for r in state.pharma_reviews if r.programme_id == p.id and r.regulator == FDA]
    if any(r.status == "review" for r in reviews):
        return state
    if p.stage == "phase2" and approval.accelerated_ok(p, gd, b):
        state, _ = approval.file(state, p, FDA, rng, b, gd)
        return state
    nxt = pipeline.next_trial(p)
    if nxt is not None and p.stage != "submission":
        return pipeline.with_programme(state, pipeline.begin_stage(state, p, nxt, DESIGN, b, gd))
    if any(r.status == "crl" for r in reviews) and len(reviews) > 1:
        return pipeline.with_programme(state, replace(p, status="stopped"))
    state, _ = approval.file(state, p, FDA, rng, b, gd)
    return state


def _approved_turn(state: GameState, pid: int) -> int | None:
    return pd.approval_in(state, pid, FDA)


def _attrition(seed: int, data: LoadedData) -> tuple[int, int, int, int, tuple[int, ...]]:
    rng = RngFactory(seed)
    state = _cohort(_bare(data, seed, START), rng, data, "phase1", COHORT_PER_AREA, ai=False)
    state, _ = _play(state, rng, data, HORIZON)
    approved = oncology = onc_total = 0
    months: list[int] = []
    for p in state.pharma_programmes:
        t = _approved_turn(state, p.id)
        if p.area == "oncology":
            onc_total += 1
        if t is None:
            continue
        approved += 1
        oncology += p.area == "oncology"
        months.append(t - START)
    return approved, len(state.pharma_programmes), oncology, onc_total, tuple(months)


def _ai(seed: int, data: LoadedData, ai: bool) -> float:
    rng = RngFactory(seed)
    per_area = AI_COHORT // len(AREAS)
    state = _cohort(_bare(data, seed, START), rng, data, "discovery", per_area, ai=ai)
    state, spent = _play(state, rng, data, HORIZON)
    approved = sum(1 for p in state.pharma_programmes if _approved_turn(state, p.id) is not None)
    real_b = spent / (pd.BILLION * pd.CENTS * data.balance.pharma.scale)
    return approved / real_b if real_b > 0 else 0.0


def _cliff(seed: int, data: LoadedData) -> float:
    """A small-molecule blockbuster's revenue 24 months after its US LOE over the month before."""
    b, gd = data.balance, data.game_data
    approved = ym_to_turn(2026, 1)
    state = _bare(data, seed, approved)
    p = Programme(
        id=1,
        company_id=PLAYER,
        name="Blockbuster",
        indication="thrombosis",
        area="cardiovascular",
        modality="small_molecule",
        stage="approved",
        start_turn=approved,
        due_turn=approved,
        efficacy=BLOCKBUSTER_EFFICACY,
        safety=b.pharma.safety.mean,
        status="marketed",
        obs_n=3,
        obs_eff=BLOCKBUSTER_EFFICACY,
        obs_safety=b.pharma.safety.mean,
        patent_turn=approved - 10 * pd.MONTHS,
        ind_turn=approved - 8 * pd.MONTHS,
        filed_turn=approved - pd.MONTHS,
        approved_turn=approved,
    )
    rows = [Authorisation(1, r.key, r.region, approved) for r in pd.regulators(gd)]
    rows += [
        Authorisation(1, pd.RELY + region, region, approved)
        for region in gd.region_keys
        if pd.reliance_share(gd, region) > 0
    ]
    ind = pd.indication(gd, "thrombosis")
    state = replace(
        state,
        pharma_programmes=(p,),
        pharma_authorisations=tuple(rows),
        pharma_drugs=(Drug(1, round(ind.price_year * pd.CENTS), 1.0, approved),),
    )
    ends = [pd.loe_turn(state, p, region, gd) for region in gd.region_keys]
    assert all(e is not None for e in ends)
    first = min(e for e in ends if e is not None)
    last = max(e for e in ends if e is not None)
    covered = tuple(
        Hta(1, r.region, 0, 0, "covered", 0) for r in pd.file(gd).pricing.regions if r.hta
    )
    revenue: dict[int, int] = {}
    for t in (first - 1, last + 24):
        _, _, out = demand.month(replace(state, turn=t, pharma_hta=covered), b, gd)
        revenue[t] = sum(out.revenue.values())
    before, after = revenue[first - 1], revenue[last + 24]
    return 1 - after / before if before else 0.0


def one(seed: int) -> SeedResult:
    data = loaded()
    approved, total, onc, onc_total, months = _attrition(seed, data)
    return SeedResult(
        seed=seed,
        approved=approved,
        total=total,
        oncology_approved=onc,
        oncology_total=onc_total,
        months_to_approval=months,
        cliff_loss=_cliff(seed, data),
        ai_per_b=_ai(seed, data, True),
        plain_per_b=_ai(seed, data, False),
    )


def run(seeds: Sequence[int] = SEEDS, workers: int = 1) -> list[SeedResult]:
    if workers <= 1:
        return [one(s) for s in seeds]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, seeds))


def report(results: Sequence[SeedResult]) -> str:
    med = statistics.median
    share = med(r.approved / r.total for r in results)
    onc = med(r.oncology_approved / r.oncology_total for r in results)
    below = 1 - onc / share if share else 0.0
    months = [m for r in results for m in r.months_to_approval]
    years = med(months) / pd.MONTHS if months else 0.0
    cliff = med(r.cliff_loss for r in results)
    lift = med(r.ai_per_b / r.plain_per_b - 1 for r in results if r.plain_per_b > 0)
    rows = [
        Row("1", "history holds", "unit tests; golden; history fingerprint", "identical", True),
        Row("2", "Phase I to approval", f"{share:.1%} (median)", "6-12%", 0.06 <= share <= 0.12),
        Row("2", "oncology below the average", f"{below:.0%} ({onc:.1%})", "30%+", below >= 0.3),
        Row(
            "3",
            "Phase I start to approval",
            f"{years:.1f} years (median)",
            "7-11",
            7 <= years <= 11,
        ),
        Row("4", "cliff: revenue lost in 24 months", f"{cliff:.0%} (median)", "70%+", cliff >= 0.7),
        Row(
            "5", "AI: approvals per dollar", f"{lift:+.0%} (median)", "+10-40%", 0.1 <= lift <= 0.4
        ),
        Row("6", "turn time", "make check-timing", "within guards", True),
    ]
    return table(rows)
