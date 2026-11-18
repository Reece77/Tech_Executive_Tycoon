"""The Pharma screen's data (M42, docs/formulas.md 55.7). Public facts only, built from the
programmes' public fields (stage, design, readouts, the efficacy estimate), the data and the
engine's shown functions (pipeline.shown_chance, pipeline.estimate_range, value.explain), which
never read a molecule's hidden values.

Never a programme's or asset's `efficacy` or `safety`, a review's drawn month (`due_turn`) or
whether an advisory committee will meet before it does, an HTA's drawn month, or a seeded rule
or rival approval before it happens."""

from __future__ import annotations

from typing import Final

from tst.api.schemas.pharma import (
    AssetOut,
    CmoOut,
    DealOut,
    DrugOut,
    ExclusivityOut,
    FactOut,
    HtaOut,
    IndicationOut,
    InspectionOut,
    MonthPointOut,
    PharmaOut,
    PlantOut,
    ProgrammeOut,
    RangeOut,
    ReadoutOut,
    RecallOut,
    RegulatorOut,
    ReviewOut,
    RivalApprovalOut,
    RivalDrugOut,
    RivalOut,
    RuleOut,
    ValueOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.money import format_money
from tst.sim.pharma import approval, demand, pipeline, rivals, value
from tst.sim.pharma import data as pd
from tst.sim.pharma.config import DESIGNS, MODALITIES, TRIALS
from tst.sim.pharma.models import Asset, Programme
from tst.sim.state import GameState, group_companies

HISTORY_POINTS: Final = 60  # months of revenue shown on a drug's chart


def _region_label(data: GameData, key: str) -> str:
    return next((r.label for r in data.regions if r.key == key), key.replace("_", " "))


def _range(lo: float, hi: float) -> RangeOut:
    return RangeOut(lo=round(lo, 3), hi=round(hi, 3))


def _between(start: int, r: tuple[float, float]) -> str:
    return f"{format_turn(start + round(r[0]))} to {format_turn(start + round(r[1]))}"


def _months(r: tuple[float, float]) -> str:
    return f"{round(r[0])}-{round(r[1])} months"


def _asset_range(a: Asset, balance: Balance) -> RangeOut:
    """An asset's estimate (public): its readouts' observed mean, or the prior's range."""
    eb = balance.pharma.efficacy
    if a.obs_n == 0:
        return _range(max(0.0, eb.mean - 2 * eb.sd), min(1.0, eb.mean + 2 * eb.sd))
    from tst.sim.pharma.config import TRIALS as T

    sd = balance.pharma.readout.noise[T[min(a.obs_n, len(T)) - 1]]
    half = 2 * sd / a.obs_n**0.5
    return _range(max(0.0, a.obs_eff - half), min(1.0, a.obs_eff + half))


def _explain_value(v: value.Value) -> str:
    return (
        f"Chance to approval {v.chance_lo:.0%}-{v.chance_hi:.0%}: each remaining stage's chance "
        "at the efficacy estimate's ends, times the submission's. rNPV: that chance x the present "
        f"value of sales ramping to {format_money(v.peak_lo_cents)}-"
        f"{format_money(v.peak_hi_cents)} a year at peak, less {format_money(v.cost_left_cents)} "
        f"of trials still to run (each x the chance of reaching it), discounted over "
        f"{v.years_to_launch:.1f} years to launch."
    )


def programme_out(state: GameState, p: Programme, balance: Balance, data: GameData) -> ProgrammeOut:
    ind = pd.indication(data, p.indication)
    lo, hi = pipeline.estimate_range(p, balance)
    nxt = pipeline.next_trial(p) if p.status == "ready" else None
    next_chance = next_cost = next_months = redo = None
    if nxt is not None:
        c = pipeline.shown_chance(p, nxt, "standard", balance, data)
        next_chance = _range(*c)
        next_months = pipeline.stage_months(p, nxt, "standard", balance, data)
        n = pipeline.stage_patients(nxt, "standard", data)
        next_cost = pipeline.stage_cost_cents(p, nxt, n, next_months, balance, data)
    elif p.status == "failed" and p.stage in TRIALS:
        c = pipeline.shown_chance(p, p.stage, "standard", balance, data)
        next_chance = _range(*c)
        months = pipeline.stage_months(p, p.stage, "standard", balance, data)
        n = pipeline.stage_patients(p.stage, "standard", data)
        cost = pipeline.stage_cost_cents(p, p.stage, n, months, balance, data)
        redo = round(cost * (1 + balance.pharma.redesign_cost_share))
    can_file = []
    for reg in pd.regulators(data):
        if approval.can_file(p, data, balance, reg.key) is not None:
            continue
        if any(
            r.programme_id == p.id and r.regulator == reg.key and r.status in ("review", "approved")
            for r in state.pharma_reviews
        ):
            continue
        can_file.append(reg.key)
    reviews = []
    for r in state.pharma_reviews:
        if r.programme_id != p.id:
            continue
        rng = (
            pd.file(data).approval.crl_resubmit_months
            if r.resubmission
            else approval.review_range(data, r.regulator, r.priority)
        )
        expected = _between(r.filed_turn, rng)
        adcom = None
        if r.adcom_positive is not None:
            adcom = "in favour" if r.adcom_positive else "against"
        reviews.append(
            ReviewOut(
                regulator=r.regulator,
                regulator_name=pd.regulator(data, r.regulator).name,
                application=r.application,
                filed=format_turn(r.filed_turn),
                status=r.status,
                priority=r.priority,
                expected=expected,
                adcom=adcom,
                decided=format_turn(r.decided_turn) if r.decided_turn is not None else None,
            )
        )
    approvals = sorted(
        {
            pd.regulator(data, a.authority).name
            if not a.authority.startswith(pd.RELY)
            else _region_label(data, a.region) + " (reliance)"
            for a in state.pharma_authorisations
            if a.programme_id == p.id and a.from_turn <= state.turn
        }
    )
    exclusivity = []
    for region in data.region_keys:
        loe = pd.loe_turn(state, p, region, data)
        exclusivity.append(
            ExclusivityOut(
                region=region,
                region_label=_region_label(data, region),
                ends=format_turn(loe) if loe is not None else None,
                ended=loe is not None and state.turn >= loe,
            )
        )
    v = None
    if p.status in ("active", "ready", "failed"):
        x = value.explain(p, balance, data)
        v = ValueOut(
            to_approval=_range(x.chance_lo, x.chance_hi),
            rnpv_lo_cents=x.rnpv_lo_cents,
            rnpv_hi_cents=x.rnpv_hi_cents,
            peak_lo_cents=x.peak_lo_cents,
            peak_hi_cents=x.peak_hi_cents,
            cost_left_cents=x.cost_left_cents,
            years_to_launch=round(x.years_to_launch, 1),
            explain=_explain_value(x),
        )
    history = [
        ReadoutOut(
            stage=r.stage,
            month=format_turn(r.turn),
            success=r.success,
            shown=_range(r.chance_lo, r.chance_hi),
            observed=round(r.observed, 3),
            design=r.design,
        )
        for r in state.pharma_readouts
        if r.programme_id == p.id
    ]
    partner = state.company(p.partner_id).name if p.partner_id is not None else None
    return ProgrammeOut(
        id=p.id,
        company=state.company(p.company_id).name,
        name=p.name,
        indication=p.indication,
        indication_label=ind.label,
        area=p.area,
        modality=p.modality,
        stage=p.stage,
        status=p.status,
        design=p.design,
        patients=p.patients,
        started=format_turn(p.start_turn),
        planned_end=format_turn(p.due_turn),
        cost_cents=p.cost_cents,
        spent_cents=p.spent_cents,
        ai=p.ai,
        origin=p.origin,
        efficacy=_range(lo, hi),
        readouts=p.obs_n,
        next_stage=nxt,
        next_chance=next_chance,
        next_cost_cents=next_cost,
        next_months=next_months,
        redesign_cost_cents=redo,
        can_file=can_file,
        breakthrough=p.breakthrough,
        accelerated=p.accelerated,
        orphan=ind.orphan,
        partner=partner,
        history=history,
        reviews=reviews,
        approvals=approvals,
        exclusivity=exclusivity,
        value=v,
    )


def _drug_out(state: GameState, p: Programme, balance: Balance, data: GameData) -> DrugOut | None:
    drug = demand.drug_of(state, p.id)
    if drug is None:
        return None
    ind = pd.indication(data, p.indication)
    months = [m for m in state.pharma_months if m.programme_id == p.id]
    last = months[-1] if months else None
    year = sum(m.revenue_cents for m in months if m.turn > state.turn - pd.MONTHS)
    pick = next((i for i in state.pharma_ira if i.programme_id == p.id), None)
    lo, hi = pd.file(data).pricing.hta_months
    hta = [
        HtaOut(
            region=_region_label(data, h.region),
            status=h.status,
            expected=_between(h.requested_turn, (lo, hi)),
        )
        for h in state.pharma_hta
        if h.programme_id == p.id
    ]
    return DrugOut(
        programme_id=p.id,
        name=p.name,
        indication_label=ind.label,
        modality=p.modality,
        list_cents=drug.list_cents,
        reference_cents=round(ind.price_year * pd.CENTS),
        support=drug.support,
        patients=round(last.patients, 1) if last else 0.0,
        revenue_cents=last.revenue_cents if last else 0,
        year_cents=year,
        generic=bool(last and last.generic),
        ira=(
            f"Negotiated Medicare price from January {pick.year}, about {pick.discount:.0%} lower"
            if pick
            else None
        ),
        hta=hta,
        history=[
            MonthPointOut(
                month=format_turn(m.turn),
                revenue_cents=m.revenue_cents,
                us_cents=m.us_cents,
                patients=round(m.patients, 1),
            )
            for m in months[-HISTORY_POINTS:]
        ],
        blocked=state.turn < drug.blocked_until,
    )


def _rivals(state: GameState, balance: Balance, data: GameData) -> list[RivalOut]:
    out = []
    for cid, r in sorted(rivals.companies(state, data).items()):
        c = state.company(cid)
        approvals = [
            RivalApprovalOut(
                name=s.name, area=s.area, modality=s.modality, month=format_turn(s.approved_turn)
            )
            for s in state.pharma_seeded
            if s.company_id == cid and s.approved_turn <= state.turn
        ]
        out.append(
            RivalOut(
                id=cid,
                name=c.name,
                generics=r.generics,
                year_cents=sum(c.mrr_history[-pd.MONTHS :]),
                drugs=[
                    RivalDrugOut(
                        name=d.name,
                        indication_label=pd.indication(data, d.indication).label,
                        approved=d.approved,
                        loe_us=d.loe_us,
                    )
                    for d in r.drugs
                ],
                pipeline=list(r.pipeline),
                approvals=approvals[-10:],
            )
        )
    return out


def pharma_out(state: GameState, loaded: LoadedData) -> PharmaOut:
    b, d = loaded.balance, loaded.game_data
    pf = pd.file(d)
    ids = {c.id for c in group_companies(state, state.player.id)}
    player = state.player.id
    turn = state.turn
    mine = [p for p in state.pharma_programmes if p.company_id in ids or p.partner_id in ids]
    out_licensed = {
        x.programme_id
        for x in state.pharma_deals
        if x.kind == "out_license" and x.company_id in ids
    }
    mine += [p for p in state.pharma_programmes if p.id in out_licensed and p not in mine]
    indications = [
        IndicationOut(
            key=i.key,
            label=i.label,
            area=i.area,
            area_label=pd.area(d, i.area).label,
            orphan=i.orphan,
            market_cents=pd.cents(pd.market_b(d, i, turn) * pd.BILLION, b),
            prevalence_m=i.prevalence_m,
            price_cents=round(i.price_year * pd.CENTS),
        )
        for i in pf.indications
    ]
    regulators = []
    for r in pd.regulators(d):
        rev = pd.review_def(d, r.key)
        regulators.append(
            RegulatorOut(
                key=r.key,
                name=r.name,
                region=_region_label(d, r.region),
                application=rev.application,
                standard=_months(rev.standard_months),
                priority=_months(rev.priority_months) if rev.priority_months else None,
            )
        )
    drugs = [x for p in mine if (x := _drug_out(state, p, b, d)) is not None]
    plants = [
        PlantOut(
            id=pl.id,
            kind=pl.kind,
            label=pf.plant(pl.kind).label,
            region=_region_label(d, pl.region),
            ordered=format_turn(pl.ordered_turn),
            ready=format_turn(pl.ready_turn),
            live=pl.ready_turn <= turn and not pl.closed,
            quality=pl.quality,
            capex_cents=pl.capex_cents,
            patient_years_k=pf.plant(pl.kind).capacity,
        )
        for pl in state.pharma_plants
        if pl.company_id in ids
    ]
    chosen: dict[str, list[str]] = {}
    for kind in ("api", "biologics"):
        chosen.setdefault(demand._cmo(state, player, kind, d), []).append(kind)
    cmos = [
        CmoOut(
            name=c.name,
            region=_region_label(d, c.region),
            kinds=list(c.kinds),
            quality=c.quality,
            chosen_for=chosen.get(c.name, []),
        )
        for c in pf.cmos
    ]
    mult = pf.licensing.acquire_mult
    assets = [
        AssetOut(
            id=a.id,
            name=a.name,
            indication_label=pd.indication(d, a.indication).label,
            area=a.area,
            modality=a.modality,
            stage=a.stage,
            efficacy=_asset_range(a, b),
            upfront_cents=a.upfront_cents,
            milestones_cents=a.milestones_cents,
            royalty=a.royalty,
            acquire_cents=round((a.upfront_cents + a.milestones_cents) * mult),
            until=format_turn(a.until_turn),
        )
        for a in state.pharma_assets
        if a.taken_by is None and turn < a.until_turn
    ]
    deals = [
        DealOut(
            id=x.id,
            kind=x.kind,
            counterparty=x.counterparty,
            programme=next(
                (p.name for p in state.pharma_programmes if p.id == x.programme_id), None
            ),
            signed=format_turn(x.turn),
            upfront_cents=x.upfront_cents,
            milestones_cents=x.milestones_cents,
            royalty=x.royalty,
            fee_cents=x.fee_cents,
            until=format_turn(x.until_turn) if x.until_turn is not None else None,
        )
        for x in state.pharma_deals
        if x.company_id in ids
    ]
    inspections = [
        InspectionOut(
            regulator=pd.regulator(d, i.regulator).name,
            month=format_turn(i.turn),
            finding=i.finding,
            until=format_turn(i.until_turn) if i.until_turn > i.turn else None,
            fine_cents=i.fine_cents,
        )
        for i in state.pharma_inspections
        if i.company_id in ids
    ]
    names = {p.id: p.name for p in state.pharma_programmes}
    recalls = [
        RecallOut(
            programme=names.get(r.programme_id, "?"),
            month=format_turn(r.turn),
            cost_cents=r.cost_cents,
        )
        for r in state.pharma_recalls
        if r.programme_id in {p.id for p in mine}
    ]
    rules = []
    for rule in state.pharma_rules:
        if rule.kind == "ira_round":
            text = f"Medicare negotiation: {rule.drugs} drugs, about {rule.discount:.0%} lower"
        else:
            text = "Small molecules now wait 13 years for negotiation, as biologics do"
        rules.append(RuleOut(year=rule.year, text=text))
    facts = [
        FactOut(month=format_turn(month_to_turn(f.month)), text=f.text)
        for f in pf.history
        if month_to_turn(f.month) <= turn
    ]
    return PharmaOut(
        engaged=pd.engaged(state, d),
        ai_ready=pipeline.ai_ready(state, player, b, d),
        discovery_slots=pipeline.discovery_slots(state, player, b, d),
        in_discovery=pipeline.in_discovery(state, player),
        researchers=pipeline.researchers(state, player, b),
        indications=indications,
        modalities=list(MODALITIES),
        designs=list(DESIGNS),
        regulators=regulators,
        programmes=[programme_out(state, p, b, d) for p in mine],
        drugs=drugs,
        plants=plants,
        cmos=cmos,
        assets=assets,
        deals=deals,
        inspections=inspections,
        recalls=recalls,
        rivals=_rivals(state, b, d),
        rules=rules,
        facts=facts,
    )
