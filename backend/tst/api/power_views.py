"""Building the Power API's responses (M32, docs/formulas.md 46.9) from the state. The player's
group only; published figures. A building plant shows its quote and what has been paid, never its
true capex or completion; a queue shows the region's range, never a draw."""

from __future__ import annotations

from typing import Final

from tst.api.schemas.power import (
    GridOutageOut,
    PlantMonthOut,
    PlantQuoteOut,
    PlantTypeOut,
    PowerMonthOut,
    PowerPlantOut,
    PowerRegionOut,
    PowerScreenOut,
    PowerSiteOut,
    PpaOut,
    PpaQuoteOut,
    QueueOut,
    SellerOut,
    SiteOptionOut,
    SitingOut,
)
from tst.loader import LoadedData
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import SimError
from tst.sim.facilities.lifecycle import facility_name
from tst.sim.group.assets import group_ids
from tst.sim.power import demand, grid, outages, plants, ppa, queues, siting
from tst.sim.power.actions import SITE_KINDS, BuildPlant, check_build
from tst.sim.power.models import Plant, PowerMonth
from tst.sim.state import GameState

CENTS: Final = 100  # tunable-exempt: cents a dollar
MONTHS: Final = 12  # tunable-exempt: calendar
CHOICES: Final = ("gas", "solar_storage", "wind")  # tunable-exempt: the cheapest-plant set


def _latest(state: GameState, company: int, region: str) -> PowerMonth | None:
    months = [m for m in state.power_months if m.company_id == company and m.region == region]
    return max(months, key=lambda m: m.turn) if months else None


def _status(state: GameState, p: Plant) -> str:
    f = plants.facility_of(state, p)
    if p.live(state.turn):
        return "offline" if p.offline(state.turn) else "live"
    if f.capex_paid_cents >= f.capex_cents and not p.connected:
        return "waiting for the grid"
    return "building"


def plant_out(state: GameState, p: Plant, b: Balance, d: GameData) -> PowerPlantOut:
    f = plants.facility_of(state, p)
    t = plants.type_def(d, p.type)
    q = queues.entry_for(state, p.facility_id)
    lo = hi = None
    if q is not None and q.connected_turn is None:
        lo, hi = queues.shown_range(q.median_months, b)
    site = state.facility(p.site_id) if p.site_id is not None else None
    m = p.month
    cf = plants.capacity_factor(t, f.region)
    return PowerPlantOut(
        facility_id=p.facility_id,
        name=plants.plant_name(state, p, d),
        type=p.type,
        type_label=t.label,
        mw=p.mw,
        region=f.region,
        region_label=d.region(f.region).label,
        city=f.city,
        site_id=p.site_id,
        site_name=facility_name(site, b, d) if site is not None else None,
        status=_status(state, p),
        estimate_cents=p.estimate_cents,
        paid_cents=f.capex_paid_cents,
        expected_turn=p.live_turn if p.live_turn is not None else max(f.ready_turn, state.turn),
        live_turn=p.live_turn,
        queue_lo_months=lo,
        queue_hi_months=hi,
        queued_months=state.turn - q.joined_turn if q and q.connected_turn is None else None,
        capacity_factor=cf,
        mwh_year=p.mw * 8760 * cf,
        levelised_usd_mwh=plants.levelised(state, p.type, f.region, b, d),
        intensity=t.intensity_at(grid.year_of(state.turn)),
        outage_until=p.outage_until if p.offline(state.turn) else None,
        month=PlantMonthOut(
            turn=m.turn,
            output_mwh=m.output_mwh,
            used_mwh=m.used_mwh,
            exported_mwh=m.exported_mwh,
            curtailed_mwh=m.curtailed_mwh,
            fuel_cents=m.fuel_cents,
            om_cents=m.om_cents,
            carbon_cents=m.carbon_cents,
            grid_charge_cents=m.grid_charge_cents,
            export_cents=m.export_cents,
            displaced_cents=m.displaced_cents,
            tonnes=m.tonnes,
            offline=m.offline,
        )
        if m is not None
        else None,
    )


def power_out(state: GameState, data: LoadedData) -> PowerScreenOut:
    b, d = data.balance, data.game_data
    player = state.player.id
    group = group_ids(state)
    pb = b.power
    regions = []
    for r in d.region_keys:
        m = _latest(state, player, r)
        lo, hi = queues.shown_range(queues.median_months(state, r, d), b)
        costs = {k: plants.levelised(state, k, r, b, d) for k in CHOICES}
        best = min(costs, key=lambda k: costs[k])
        regions.append(
            PowerRegionOut(
                region=r,
                label=d.region(r).label,
                grid_usd_mwh=grid.price_cents(state, r, b, d) / CENTS,
                carbon_usd_t=grid.carbon_price(state, r, d),
                intensity=grid.intensity(state, r, d),
                queue_lo_months=lo,
                queue_hi_months=hi,
                outages_a_year=outages.rate(state, r, b, d),
                demand_mwh=m.demand_mwh if m else 0.0,
                plant_mwh=m.plant_mwh if m else 0.0,
                ppa_mwh=m.ppa_mwh if m else 0.0,
                grid_mwh=m.grid_mwh if m else 0.0,
                exported_mwh=m.exported_mwh if m else 0.0,
                peak_mw=m.peak_mw if m else 0.0,
                grid_cents=m.grid_cents if m else 0,
                net_cents=m.net_cents if m else 0,
                scope1_tonnes=m.scope1_tonnes if m else 0.0,
                scope2_tonnes=m.scope2_tonnes if m else 0.0,
                cheapest_plant=best,
                cheapest_usd_mwh=costs[best],
            )
        )
    history = [
        PowerMonthOut(
            turn=m.turn,
            region=m.region,
            demand_mwh=m.demand_mwh,
            plant_mwh=m.plant_mwh,
            ppa_mwh=m.ppa_mwh,
            grid_mwh=m.grid_mwh,
            exported_mwh=m.exported_mwh,
            grid_cents=m.grid_cents,
            net_cents=m.net_cents,
            scope1_tonnes=m.scope1_tonnes,
            scope2_tonnes=m.scope2_tonnes,
            outage=m.outage,
            wafers_lost=m.wafers_lost,
        )
        for m in state.power_months
        if m.company_id == player
    ]
    mine = [p for p in state.plants if p.company_id in group]
    ppas = [
        PpaOut(
            id=p.id,
            region=p.region,
            region_label=d.region(p.region).label,
            producer=p.producer,
            producer_name=(
                ppa.seller(d, p.region, p.producer) or ppa.Seller(p.producer, p.producer)
            ).name,
            mwh_month=p.mwh_month,
            price_usd_mwh=p.price_cents / CENTS,
            start_turn=p.start_turn,
            end_turn=p.end_turn,
            status=p.status,
            used_mwh=p.used_mwh,
            paid_cents=p.paid_cents,
        )
        for p in state.ppas
        if p.company_id in group
    ]
    queue = []
    for q in state.grid_queue:
        if q.company_id not in group:
            continue
        f = state.facility(q.facility_id)
        if f is None:
            continue
        plant = plants.plant_of(state, f.id)
        name = plants.plant_name(state, plant, d) if plant else facility_name(f, b, d)
        lo, hi = queues.shown_range(q.median_months, b)
        queue.append(
            QueueOut(
                id=q.id,
                facility_id=q.facility_id,
                name=name,
                kind=q.kind,
                region=q.region,
                mw=q.mw,
                joined_turn=q.joined_turn,
                lo_months=lo,
                hi_months=hi,
                connected_turn=q.connected_turn,
            )
        )
    year = grid.year_of(state.turn)
    types = []
    for t in d.power.plant_types if d.power else ():
        types.append(
            PlantTypeOut(
                key=t.key,
                label=t.label,
                capex_kw_usd=plants.capex_kw(state, t.key, b, d),
                build_months=t.build_months,
                available=plants.available(state, t.key, d),
                life_years=t.life_years,
                intensity=t.intensity_at(year),
                levelised={r: plants.levelised(state, t.key, r, b, d) for r in d.region_keys},
                capacity_factor={r: plants.capacity_factor(t, r) for r in d.region_keys},
            )
        )
    sellers = [
        SellerOut(
            region=r,
            key=s.key,
            name=s.name,
            forward_usd_mwh=ppa.forward_cents(state, r, b, d) / CENTS,
        )
        for r in d.region_keys
        for s in (ppa.sellers(d, r) if d.power else [])
    ]
    sites = [
        SiteOptionOut(
            facility_id=f.id,
            name=facility_name(f, b, d),
            kind=f.kind,
            region=f.region,
            city=f.city,
            mw=demand.facility_mw(state, f, b, d),
        )
        for f in state.facilities
        if f.company_id in group and f.kind in SITE_KINDS and f.status != "closed"
    ]
    recent = [
        m for m in state.power_months if m.company_id == player and m.turn > state.turn - MONTHS - 1
    ]
    return PowerScreenOut(
        unlocked=plants.plants_unlocked(state, player, b),
        min_stage=pb.plants.min_stage,
        sizes_mw=list(pb.plants.sizes_mw),
        ppa_years=list(range(int(pb.ppa.years.lo), int(pb.ppa.years.hi) + 1)),
        take_or_pay=pb.ppa.take_or_pay,
        regions=regions,
        history=history,
        plants=[plant_out(state, p, b, d) for p in mine],
        ppas=ppas,
        queue=queue,
        outages=[
            GridOutageOut(turn=o.turn, region=o.region, region_label=d.region(o.region).label)
            for o in state.grid_outages
        ],
        plant_types=types,
        sellers=sellers,
        sites=sites,
        scope1_year=sum(m.scope1_tonnes for m in recent),
        scope2_year=sum(m.scope2_tonnes for m in recent),
    )


def siting_out(state: GameState, data: LoadedData, kind: str, capacity: float) -> SitingOut:
    b, d = data.balance, data.game_data
    rows = siting.sites(state, state.player.id, kind, capacity, b, d)
    return SitingOut(
        kind=kind,
        size=capacity,
        mw=siting.draw_mw(kind, capacity, b, d),
        sites=[
            PowerSiteOut(
                city=s.city,
                label=s.label,
                region=s.region,
                region_label=s.region_label,
                price_usd_mwh=s.price_usd_mwh,
                queue_lo_months=s.queue_lo,
                queue_hi_months=s.queue_hi,
                carbon_usd_t=s.carbon_usd_t,
                outages_a_year=s.outages_a_year,
                behind_meter=s.behind_meter,
                cheapest_plant=s.cheapest_plant,
                cheapest_usd_mwh=s.cheapest_usd_mwh,
            )
            for s in rows
        ],
    )


def plant_quote_out(
    state: GameState,
    data: LoadedData,
    founder_id: int,
    plant_type: str,
    mw: float,
    region: str,
    site_id: int | None,
) -> PlantQuoteOut:
    b, d = data.balance, data.game_data
    action = BuildPlant(founder_id, plant_type, mw, region, None, site_id)
    reason = None
    try:
        check_build(state, state.player.id, action, b, d)
    except SimError as exc:
        reason = str(exc)
    q = plants.quote(state, plant_type, mw, region, site_id is not None, b, d)
    lo = hi = None
    if site_id is None:
        lo, hi = queues.shown_range(queues.median_months(state, region, d), b)
    return PlantQuoteOut(
        type=q.type,
        label=q.label,
        mw=q.mw,
        region=q.region,
        capex_cents=q.capex_cents,
        monthly_capex_cents=q.monthly_capex_cents,
        build_months=q.build_months,
        ready_turn=q.ready_turn,
        capacity_factor=q.capacity_factor,
        mwh_year=q.mwh_year,
        levelised_usd_mwh=q.levelised_usd_mwh,
        intensity=q.intensity,
        behind_meter=q.behind_meter,
        queue_lo_months=lo,
        queue_hi_months=hi,
        allowed=reason is None,
        reason=reason,
    )


def ppa_quote_out(
    state: GameState, data: LoadedData, region: str, producer: str, mwh: float, years: int
) -> PpaQuoteOut:
    q = ppa.quote(state, region, producer, mwh, years, data.balance, data.game_data)
    return PpaQuoteOut(
        region=q.region,
        producer=q.producer,
        producer_name=q.producer_name,
        mwh_month=q.mwh_month,
        years=q.years,
        price_usd_mwh=q.price_cents / CENTS,
        forward_usd_mwh=q.forward_cents / CENTS,
        start_turn=q.start_turn,
        end_turn=q.end_turn,
        monthly_cents=q.monthly_cents,
        minimum_cents=q.minimum_cents,
    )
