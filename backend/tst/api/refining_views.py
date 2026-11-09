"""The Refineries screen's read model (M20, formulas.md 36). Plants show their quoted capex and
what has been paid, never the facility's true capex with its hidden overrun; staff show as
counts and coverage, never skill. Unit costs and margins are the engine's (sim.refining)."""

from __future__ import annotations

from dataclasses import asdict

from tst.api.schemas.refining import (
    ChainLinkOut,
    OwnSupplyOut,
    RecipeOut,
    RefineriesOut,
    RefineryHistoryOut,
    RefineryMonthOut,
    RefineryPlantOut,
    RefineryQuoteOut,
    RefiningDealOut,
    RefiningGoodOut,
    RefiningPowerOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.chips import chips
from tst.sim.facilities import lifecycle
from tst.sim.facilities.models import Facility
from tst.sim.refining import goods as rg
from tst.sim.refining import quote as rq
from tst.sim.refining.models import PlantMonth, Refinery
from tst.sim.refining.plants import (
    group_of,
    power_index,
    process_level,
    recipe_of,
)
from tst.sim.state import GameState


def _month(pm: PlantMonth | None) -> RefineryMonthOut | None:
    if pm is None:
        return None
    values = asdict(pm)
    values["yield"] = values.pop("yield_")
    values["made"] = values.pop("output")
    values["possible"] = values.pop("capacity")
    return RefineryMonthOut(**values, margin=pm.margin)


def plant_out(
    state: GameState, ref: Refinery, facility: Facility, data: LoadedData
) -> RefineryPlantOut:
    b, d = data.balance, data.game_data
    r = recipe_of(ref, b)
    kind = b.facility.kinds[r.kind]
    staffing = lifecycle.staffing(state, facility, b)
    turn = state.turn
    return RefineryPlantOut(
        id=facility.id,
        company_id=facility.company_id,
        company=state.company(facility.company_id).name,
        name=lifecycle.facility_name(facility, b, d),
        recipe=ref.recipe,
        recipe_label=r.label,
        kind=r.kind,
        kind_label=kind.label,
        region=facility.region,
        region_label=d.region(facility.region).label,
        status=facility.status,
        size=facility.capacity,
        unit=kind.unit,
        output_unit=rg.volume_unit(r.output_good, b, d),
        input_good=r.input_good,
        input_label=rg.label(r.input_good, b, d) if r.input_good else None,
        output_good=r.output_good,
        output_label=rg.label(r.output_good, b, d),
        ready_turn=facility.ready_turn,
        ready_label=format_turn(facility.ready_turn),
        estimate_cents=ref.estimate_cents,
        capex_paid_cents=facility.capex_paid_cents,
        book_value_cents=facility.book_value_cents,
        staff=staffing.staff,
        staff_needed=staffing.needed,
        coverage=staffing.coverage,
        unit_id=facility.unit_id,
        stated_yield=r.yield_,
        semi_grade=r.semi_grade,
        curbed_until=format_turn(ref.curb_until) if ref.curbed(turn) and ref.curb_until else None,
        curb_run=ref.curb_run if ref.curbed(turn) else None,
        stopped_until=format_turn(ref.stop_until)
        if ref.stopped(turn) and ref.stop_until is not None
        else None,
        incident_open=ref.incident_turn is not None,
        incidents=ref.incidents,
        host_id=ref.host_id,
        month=_month(ref.month),
        history=[
            RefineryHistoryOut(
                turn=t, label=format_turn(t), made=o, unit_cost_cents=u, market_cents=m
            )
            for t, o, u, m in ref.history
        ],
    )


def recipes_out(state: GameState, company: int, data: LoadedData) -> list[RecipeOut]:
    b, d = data.balance, data.game_data
    out = []
    for key, r in b.refining.recipes.items():
        kind = b.facility.kinds[r.kind]
        sizes = list(kind.sizes or b.facility.sizes)
        q = lifecycle.quote(state, company, r.kind, d.region_keys[0], sizes[0], b, d)
        out.append(
            RecipeOut(
                key=key,
                label=r.label,
                kind=r.kind,
                kind_label=kind.label,
                unit=kind.unit,
                sizes=sizes,
                input_good=r.input_good,
                input_label=rg.label(r.input_good, b, d) if r.input_good else None,
                input_per_output=r.input_per_output,
                output_good=r.output_good,
                output_label=rg.label(r.output_good, b, d),
                output_unit=rg.volume_unit(r.output_good, b, d),
                **{"yield": r.yield_},
                mwh_per_unit=r.mwh_per_unit,
                build_months=kind.build_months,
                life_months=kind.life_months,
                ramp_months=r.ramp_months,
                staff_per=kind.staff_per,
                capex_per_unit_cents=round(q.capex_cents / sizes[0]),
                semi_grade=r.semi_grade,
                curbs=r.curbs,
                incident_rate=r.incident_rate,
            )
        )
    return out


def _goods(state: GameState, data: LoadedData) -> list[RefiningGoodOut]:
    b, d = data.balance, data.game_data
    keys: list[str] = []
    for r in b.refining.recipes.values():
        for g in (r.input_good, r.output_good):
            if g is not None and g not in keys:
                keys.append(g)
    return [
        RefiningGoodOut(
            key=g,
            label=rg.label(g, b, d),
            unit=rg.volume_unit(g, b, d),
            price_cents=rg.price_cents(state, g, b, d),
            allocation=rg.allocation(state, g, b, d),
        )
        for g in keys
    ]


def _chain(state: GameState, data: LoadedData) -> list[ChainLinkOut]:
    """The group's value chain (36: mine -> refinery -> wafer -> fab -> chip -> device): its
    plants by output, the group's mines (M19), its fabs (M21) and the products that use them."""
    b, d = data.balance, data.game_data
    group = group_of(state, state.player.id)
    links: list[ChainLinkOut] = []
    plants = [
        (ref, f)
        for ref in state.refineries
        if (f := state.facility(ref.facility_id)) is not None
        and f.status != "closed"
        and f.company_id in group
    ]
    products = [
        p for cid in group for p in state.company_products(cid) if p.status in ("live", "building")
    ]
    chip_products = [p for p in products if chips.is_chip(p, d)]
    device_products = [p for p in products if p.category in b.hardware.bom]
    from tst.sim.fabs.plants import node_label  # M21: fabs between wafers and chips (38.2)
    from tst.sim.mining.actions import mine_name  # M19's mines head the chain (36, 35.3)

    fabs = [
        (fab, f)
        for fab in state.fabs
        if (f := state.facility(fab.facility_id)) is not None
        and f.status != "closed"
        and f.company_id in group
    ]

    for mine in state.mines:
        if mine.company_id not in group or mine.status == "closed":
            continue
        feeds = [
            lifecycle.facility_name(g, b, d)
            for other, g in plants
            if (spec := b.refining.goods.get(recipe_of(other, b).input_good or "")) is not None
            and spec.source == mine.commodity
            and spec.priced_by == "share"
        ]
        if mine.buyer_id is not None:
            feeds.append(state.company(mine.buyer_id).name)
        links.append(
            ChainLinkOut(
                stage="mine",
                company=state.company(mine.company_id).name,
                name=mine_name(mine, d),
                detail=f"{mine.commodity}: {mine.capacity_t:,.0f} t a year, {mine.status}",
                supplies=feeds,
            )
        )
    for ref, f in plants:
        r = recipe_of(ref, b)
        feeds = [
            lifecycle.facility_name(g, b, d)
            for other, g in plants
            if recipe_of(other, b).input_good == r.output_good
        ]
        if r.output_good == b.refining.wafer.good:
            feeds += [p.name for p in chip_products]
            feeds += [lifecycle.facility_name(g, b, d) for _, g in fabs]
        else:
            mixes = b.commodity.mixes
            for p in chip_products:
                mix = mixes.get(b.chips.good)
                if mix is not None and r.output_good in mix.weights:
                    feeds.append(p.name)
            for p in device_products:
                mix = mixes.get(b.hardware.bom[p.category].good)
                if mix is not None and r.output_good in mix.weights:
                    feeds.append(p.name)
        stage = "wafer" if r.output_good == b.refining.wafer.good else "refinery"
        links.append(
            ChainLinkOut(
                stage=stage,
                company=state.company(f.company_id).name,
                name=lifecycle.facility_name(f, b, d),
                detail=f"{r.label}: {f.capacity:,} {b.facility.kinds[r.kind].unit}",
                supplies=feeds,
            )
        )
    for fab, f in fabs:
        links.append(
            ChainLinkOut(
                stage="fab",
                company=state.company(f.company_id).name,
                name=lifecycle.facility_name(f, b, d),
                detail=f"{node_label(d, fab.node)}: {f.capacity:,} wafer starts a month",
                supplies=[p.name for p in chip_products if p.company_id == f.company_id],
            )
        )
    for p in chip_products:
        chip_type = d.category(p.category).chip_type
        feeds = [
            q.name
            for q in device_products
            if b.hardware.bom[q.category].chip_type == chip_type and q.company_id == p.company_id
        ]
        links.append(
            ChainLinkOut(
                stage="chip",
                company=state.company(p.company_id).name,
                name=p.name,
                detail=d.category(p.category).label,
                supplies=feeds,
            )
        )
    for p in device_products:
        links.append(
            ChainLinkOut(
                stage="device",
                company=state.company(p.company_id).name,
                name=p.name,
                detail=d.category(p.category).label,
                supplies=[],
            )
        )
    return links


def refineries_out(state: GameState, data: LoadedData) -> RefineriesOut:
    b, d = data.balance, data.game_data
    group = group_of(state, state.player.id)
    plants = [
        plant_out(state, ref, f, data)
        for ref in state.refineries
        if (f := state.facility(ref.facility_id)) is not None and ref.company_id in group
    ]
    names = {c.id: c.name for c in state.companies}
    deals = [
        RefiningDealOut(
            id=x.id,
            company_id=x.company_id,
            side=x.side,
            good=x.good,
            good_label=rg.label(x.good, b, d),
            unit=rg.volume_unit(x.good, b, d),
            signed_turn=x.signed_turn,
            end_label=format_turn(x.end_turn),
            monthly_volume=x.monthly_volume,
            price_cents=x.price_cents,
            taken=x.taken,
            last_taken=x.last_taken,
            charged_cents=x.charged_cents,
            status=x.status,
        )
        for x in state.refining_deals
        if x.company_id in group
    ]
    supply = []
    for s in state.own_supply:
        if s.buyer_id not in group:
            continue
        product = state.product(s.product_id) if s.product_id is not None else None
        supply.append(
            OwnSupplyOut(
                facility_id=s.facility_id,
                seller=names.get(s.seller_id, "?"),
                buyer=names.get(s.buyer_id, "?"),
                good=s.good,
                good_label=rg.label(s.good, b, d),
                product=product.name if product else None,
                volume=s.volume,
                taken=s.taken,
                unit_cents=s.unit_cents,
                market_cents=s.market_cents,
            )
        )
    rb = b.refining
    return RefineriesOut(
        plants=plants,
        recipes=recipes_out(state, state.player.id, data),
        goods=_goods(state, data),
        deals=deals,
        supply=supply,
        chain=_chain(state, data),
        power=[
            RefiningPowerOut(region=r, label=d.region(r).label, index=power_index(state, r, d))
            for r in d.region_keys
        ],
        process_level=process_level(state, state.player.id, b, d),
        semi_min_level=rb.semi_min_level,
        deal_months_low=int(rb.deal.months.lo),
        deal_months_high=int(rb.deal.months.hi),
        build_energy=rb.build_energy,
        deal_energy=rb.deal.energy,
    )


def quote_out(
    state: GameState, recipe: str, region: str, capacity: int, data: LoadedData
) -> RefineryQuoteOut:
    from tst.sim.refining.actions import quote

    b, d = data.balance, data.game_data
    company = state.player.id
    q = quote(state, company, recipe, region, capacity, b, d).quote
    e = rq.estimate(state, company, recipe, region, b, d, capacity)
    return RefineryQuoteOut(
        recipe=recipe,
        region=region,
        size=capacity,
        capex_cents=q.capex_cents,
        monthly_capex_cents=q.monthly_capex_cents,
        build_months=q.build_months,
        staff_needed=q.staff_needed,
        power_index=e.power_index,
        **{"yield": e.yield_},
        input_cents=e.input_cents,
        power_cents=e.power_cents,
        other_cents=e.other_cents,
        fixed_cents=e.fixed_cents,
        depreciation_cents=e.depreciation_cents,
        unit_cost_cents=e.unit_cost_cents,
        market_cents=e.market_cents,
        margin=e.margin,
    )
