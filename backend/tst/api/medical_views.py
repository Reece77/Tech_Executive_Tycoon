"""The Medical screen's data (M41, docs/formulas.md 50.7). Public facts only: the player's
devices with their class, route and evidence; submissions by regulator with their stage and the
route's review range; studies' designs (and their chance as a range while running) and results
once read out; coverage decisions and their windows; adoption; inspections and recalls that
happened; plants' quality systems; rivals' products and shares; dated rules.

Never a submission's drawn month (`Submission.due_turn`) or whether more information will be
asked before it is (`more_info`), a coverage decision's drawn month, a study's chance as a
number, or any inspection, recall or review-drift draw."""

from __future__ import annotations

from typing import Final

from tst.api.schemas.medical import (
    DatedRuleOut,
    DeviceOut,
    HealthRegulatorOut,
    InspectionOut,
    MedicalOut,
    PlantOut,
    RecallOut,
    RegionOut,
    RivalProductOut,
    RouteOut,
    StudyKindOut,
    StudyOut,
    SubcategoryOut,
    UseOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.medical import coverage, gate, quality, routes, studies
from tst.sim.medical import data as md
from tst.sim.medical.config import RouteDef, UseDef
from tst.sim.money import format_money
from tst.sim.products.models import Product
from tst.sim.state import GameState, group_companies

FINDING_WORDS: Final = {
    "none": "no findings",
    "observations": "observations (Form 483)",
    "warning_letter": "warning letter",
    "import_ban": "import ban",
    "consent_decree": "consent decree",
}
STATUS: Final = {"review": "review", "more_info": "information_requested"}


def _region_label(data: GameData, key: str) -> str:
    return next((r.label for r in data.regions if r.key == key), key.replace("_", " "))


def review_explain(
    state: GameState, use: UseDef, route: RouteDef, pccp: bool, balance: Balance, data: GameData
) -> tuple[str, str]:
    """A route's review range and how it is made (the data's window, a request's months and a
    change control plan's), for Explain."""
    lo, hi = routes.shown_range(state, use, route, pccp, balance, data)
    wlo, whi = md.window(state, use, route, state.turn, data)
    parts = [f"{route.label}: {wlo}-{whi} months of review"]
    if route.more_info.chance > 0:
        mlo, mhi = route.more_info.months
        parts.append(
            f"plus {mlo}-{mhi} months when the regulator asks for more information "
            f"(about {route.more_info.chance:.0%} of files, medical.yaml)"
        )
    if pccp:
        parts.append(f"plus {balance.medical.review.pccp_months} for the change control plan")
    if route.fee_cents:
        parts.append(f"fee {format_money(route.fee_cents)}")
    return f"{lo}-{hi} months", "; ".join(parts)


def _routes(
    state: GameState, product: Product, use: UseDef | None, balance: Balance, data: GameData
) -> list[RouteOut]:
    out: list[RouteOut] = []
    design = md.design_of(state, product.id)
    for reg in md.health_regulators(data):
        subs = [
            s
            for s in state.med_submissions
            if s.product_id == product.id and s.regulator == reg.key
        ]
        last = max(subs, key=lambda s: s.id) if subs else None
        if use is None:
            continue
        route = (
            md.file(data).route(last.route)
            if last is not None and last.status in routes.OPEN_STATUSES
            else md.route_for(state, use, reg.key, state.turn, data)
        )
        pccp = bool(design and design.pccp)
        review, explain = review_explain(state, use, route, pccp, balance, data)
        status = "not_filed"
        if last is not None:
            status = STATUS.get(last.status, last.status)
            if last.status == "withdrawn":
                status = "not_filed"
        cleared = md.cleared(state, product.id, reg.key, state.turn)
        if cleared and status in ("not_filed", "refused"):
            status = "cleared"
        out.append(
            RouteOut(
                regulator=reg.key,
                regulator_name=reg.name,
                route=route.key,
                label=route.label,
                review=review,
                explain=explain,
                fee_cents=route.fee_cents,
                status=status,
                filed=format_turn(last.filed_turn) if last else None,
                decided=format_turn(last.decided_turn)
                if last and last.decided_turn is not None
                else None,
                months_in=state.turn - last.filed_turn
                if last and last.status in routes.OPEN_STATUSES
                else None,
                blocker=routes.why_not(state, product, reg.key, balance, data),
            )
        )
    return out


def _studies(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> list[StudyOut]:
    out: list[StudyOut] = []
    per = md.file(data).studies.cost_per_patient_cents[product.category]
    for s in state.med_studies:
        if s.product_id != product.id:
            continue
        shown = None
        if s.status == "running":
            lo, hi = studies.shown_chance(state, product, s.kind, balance, data)
            shown = f"{lo:.0%}-{hi:.0%}"
        months = s.due_turn - s.start_turn
        explain = (
            f"{s.patients} patients x {format_money(per)} a patient = {format_money(s.cost_cents)}"
            f", spent evenly over {months} months to the readout"
        )
        out.append(
            StudyOut(
                id=s.id,
                kind=s.kind,
                patients=s.patients,
                started=format_turn(s.start_turn),
                readout=format_turn(s.due_turn),
                cost_cents=s.cost_cents,
                spent_cents=s.spent_cents,
                status=s.status,
                success_range=shown,
                explain=explain,
            )
        )
    return out


def _regions(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> list[RegionOut]:
    sub = md.subcategory(data, product.category)
    assert sub is not None
    out: list[RegionOut] = []
    for region in data.region_keys:
        who = sorted(
            {
                md.regulator(data, c.authority).name
                if not c.authority.startswith(md.RELY)
                else "registration by reliance"
                for c in state.med_clearances
                if c.product_id == product.id and c.region == region and c.from_turn <= state.turn
            }
        )
        pending = any(
            c.product_id == product.id and c.region == region and c.from_turn > state.turn
            for c in state.med_clearances
        )
        cleared = (
            ", ".join(who) if who else ("registration under way" if pending else "not cleared")
        )
        cov = coverage.coverage_of(state, product.id, region)
        status = "not_needed" if not sub.needs_coverage else (cov.status if cov else "none")
        window = None
        if sub.needs_coverage and (cov is None or cov.status != "covered"):
            lo, hi = coverage.window(state, product, region, data)
            window = f"{lo}-{hi} months"
        adopt = coverage.adoption(state, product.id, region) if sub.clinicians else None
        out.append(
            RegionOut(
                region=region,
                label=_region_label(data, region),
                cleared=cleared,
                sells_share=round(gate.share(state, product, region, balance, data), 3),
                coverage=status,
                coverage_window=window,
                adoption=round(adopt, 3) if adopt is not None else None,
            )
        )
    return out


def device_out(state: GameState, product: Product, balance: Balance, data: GameData) -> DeviceOut:
    sub = md.subcategory(data, product.category)
    assert sub is not None
    design = md.design_of(state, product.id)
    use = sub.use(design.use) if design is not None else None
    return DeviceOut(
        product_id=product.id,
        name=product.name,
        category=product.category,
        category_label=sub.label,
        status=product.status,
        quality=round(product.quality, 1),
        use=use.key if use else None,
        use_label=use.label if use else None,
        us_class=md.us_class(use, state.turn) if use else None,
        eu_class=md.eu_class(use, state.turn, data) if use else None,
        evidence=round(design.evidence, 2) if design else 0.0,
        pccp=bool(design and design.pccp),
        training_cents=design.training_cents if design else 0,
        surveillance=bool(design and design.surveillance),
        update_needed=routes.update_needed(state, product, balance, data),
        routes=_routes(state, product, use, balance, data),
        studies=_studies(state, product, balance, data),
        regions=_regions(state, product, balance, data),
        recalls=[
            RecallOut(
                turn=format_turn(r.turn),
                klass=r.klass,
                units=r.units,
                cost_cents=r.cost_cents,
                caught_early=r.caught_early,
            )
            for r in state.med_recalls
            if r.product_id == product.id
        ],
        quality_level=quality.product_level(state, product, balance, data),
    )


def medical_out(state: GameState, data: LoadedData) -> MedicalOut:
    b, d = data.balance, data.game_data
    mf = md.file(d)
    ids = {c.id for c in group_companies(state, state.player.id)}
    devices = [
        device_out(state, p, b, d)
        for p in state.products
        if p.company_id in ids and md.is_medical(p, d) and p.status != "retired"
    ]
    subs = [
        SubcategoryOut(
            key=s.key,
            label=s.label,
            consumables_cents=s.consumables_cents,
            needs_coverage=s.needs_coverage,
            clinicians=s.clinicians,
            software=s.software,
            uses=[
                UseOut(
                    key=u.key,
                    label=u.label,
                    us_class=md.us_class(u, state.turn),
                    eu_class=md.eu_class(u, state.turn, d),
                    us_route=md.route_for(state, u, md.FDA, state.turn, d).label,
                )
                for u in s.uses
            ],
        )
        for s in mf.subcategories
    ]
    plants = [
        PlantOut(
            facility_id=f,
            region=state.facility(f).region,  # type: ignore[union-attr]
            level=quality.plant_level(state, f),
            cents_month=mf.quality.levels[quality.plant_level(state, f)].cents_month,
        )
        for cid in sorted(ids)
        for f in quality.plants(state, cid, b)
    ]
    rivals: list[RivalProductOut] = []
    for s in mf.subcategories:
        rows = [
            (p, sum(x.customers for x in state.segments_of(p.id)))
            for p in state.products
            if p.category == s.key and p.status in ("live", "sunset")
        ]
        total = sum(n for _, n in rows) or 1.0
        for p, n in sorted(rows, key=lambda r: -r[1]):
            if p.company_id in ids:
                continue
            rivals.append(
                RivalProductOut(
                    company=state.company(p.company_id).name,
                    product=p.name,
                    category=s.label,
                    customers=round(n, 1),
                    share=round(n / total, 3),
                )
            )
    return MedicalOut(
        regulators=[
            HealthRegulatorOut(
                key=r.key,
                name=r.name,
                region=r.region,
                region_label=_region_label(d, r.region),
                share=round(md.part_share(d, r), 3),
            )
            for r in md.health_regulators(d)
        ],
        subcategories=subs,
        devices=devices,
        study_kinds=[
            StudyKindOut(kind=k, patients=list(v.patients), months=list(v.months))
            for k, v in mf.studies.kinds.items()
        ],
        plants=plants,
        quality_levels={k: v.cents_month for k, v in mf.quality.levels.items()},
        inspections=[
            InspectionOut(
                turn=format_turn(i.turn),
                regulator=md.regulator(d, i.regulator).name,
                finding=FINDING_WORDS[i.finding],
                until=format_turn(i.until_turn) if i.until_turn > i.turn else None,
                fine_cents=i.fine_cents,
                for_cause=i.for_cause,
            )
            for i in state.med_inspections
            if i.company_id in ids
        ],
        rivals=rivals,
        precedents=[
            DatedRuleOut(label=p.label, at=p.at, note=p.note, source=p.source)
            for p in mf.precedents
            if month_to_turn(p.at) <= state.turn
        ],
    )
