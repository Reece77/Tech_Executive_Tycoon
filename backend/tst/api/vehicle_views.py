"""Building the Vehicles API's responses (M38, docs/formulas.md 49.7) from the state: published
figures and the player's group's own books. A cell plant shows its quote and what has been paid,
never its overrun; approvals and incidents once they have happened; rivals' public line-ups and
shares. Nothing reads a draw or a seeded future."""

from __future__ import annotations

from typing import Final

from tst.api.schemas.vehicles import (
    BatteryOut,
    CarMonthOut,
    CellMakerOut,
    CellPlantOut,
    ChargingOut,
    ChemistryOut,
    CostLineOut,
    EligibilityOut,
    IncidentOut,
    LevelOptionOut,
    LevelRegionOut,
    MyCarOut,
    RivalCarOut,
    RivalShareOut,
    SubsidyOut,
    TariffOut,
    VehicleOptionsOut,
    VehiclePlantOut,
    VehicleRegionOut,
    VehicleSpecOut,
    VehiclesScreenOut,
    YearValueOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn, turn_to_ym, ym_to_turn
from tst.sim.facilities.compute import home_region_of
from tst.sim.facilities.config import month_to_turn
from tst.sim.facilities.lifecycle import facility_name, staffing
from tst.sim.group.assets import group_ids
from tst.sim.products.models import Product
from tst.sim.state import GameState
from tst.sim.vehicles import cells, charging, demand, sales, subsidies
from tst.sim.vehicles import spec as vs
from tst.sim.vehicles.config import CHEMISTRIES, LEVELS, PLATFORM_CHOICES
from tst.sim.vehicles.data import file, in_history, is_vehicle, rival_def, year_at

FIRST_YEAR: Final = 2010  # tunable-exempt: the game's first year
DECEMBER: Final = 12  # tunable-exempt: calendar


def _year_turns(state: GameState) -> list[tuple[int, int]]:
    """(year, the turn read for it): every December to the last one played, and now."""
    year, _ = turn_to_ym(state.turn)
    out = [(y, ym_to_turn(y, DECEMBER)) for y in range(FIRST_YEAR, year)]
    out.append((year, state.turn))
    return out


def _share_history(state: GameState, region: str, data: LoadedData) -> list[YearValueOut]:
    """Yearly EV shares to now: the data's in the history, the engine's from the start (only
    months already played, so nothing ahead)."""
    b, d = data.balance, data.game_data
    r = file(d).region(region)
    out = []
    for year, turn in _year_turns(state):
        if turn < b.vehicles.start_turn or turn == state.turn:
            value = (
                r.share_at(year_at(turn))
                if turn < b.vehicles.start_turn
                else demand.ev_share(state, region, b, d)
            )
            out.append(YearValueOut(year=year, value=value))
    return out


def _tariffs_into(state: GameState, region: str, data: LoadedData) -> list[TariffOut]:
    d = data.game_data
    if d.tariffs is None or d.countries is None:
        return []
    countries = {c.key for c in d.countries.countries if c.region == region}
    out = []
    for s in d.tariffs.schedules:
        if "vehicles" in s.goods and s.market in countries:
            rate = s.rate_at(state.turn)
            if rate > 0:
                out.append(TariffOut(title=s.title, origin=s.origin, market=s.market, rate=rate))
    return out


def _subsidies(state: GameState, region: str, data: LoadedData) -> list[SubsidyOut]:
    out = []
    for s in subsidies.schemes_in(state, region, data.game_data):
        cap = s.cap_at(state.turn)
        rules = [r.label for r in s.rules if month_to_turn(r.start) <= state.turn]
        out.append(
            SubsidyOut(
                title=s.title,
                country=s.country,
                amount_cents=round(s.amount_at(state.turn)),
                price_cap_cents=round(cap) if cap > 0 else None,
                rules=rules,
            )
        )
    return out


def region_out(state: GameState, region: str, data: LoadedData) -> VehicleRegionOut:
    b, d = data.balance, data.game_data
    approved = [k for k in LEVELS if k in b.vehicles.levels and vs.approved(state, region, k, b, d)]
    return VehicleRegionOut(
        region=region,
        label=d.region(region).label,
        ev_share=demand.ev_share(state, region, b, d),
        ev_share_history=_share_history(state, region, data),
        ev_sales_year=demand.ev_sales_year(state, region, b, d),
        car_sales_year=demand.car_sales(region, state.turn, d) * b.vehicles.scale,
        public_chargers=charging.public_chargers(state, region, b, d),
        coverage=demand.coverage(state, region, b, d),
        subsidies=_subsidies(state, region, data),
        tariffs=_tariffs_into(state, region, data),
        approved_levels=approved,
    )


def battery_out(state: GameState, data: LoadedData) -> BatteryOut:
    b, d = data.balance, data.game_data
    v = file(d)
    cell = cells.market_cents(state, b, d)
    share = v.battery.cell_share_at(year_at(min(state.turn, b.vehicles.start_turn - 1)))
    history = []
    for year, turn in _year_turns(state):
        if turn < b.vehicles.start_turn:
            history.append(YearValueOut(year=year, value=cells.history_cell_cents(turn, d)))
        elif turn == state.turn:
            history.append(YearValueOut(year=year, value=cell))
    at = year_at(min(state.turn, b.vehicles.start_turn - 1))
    return BatteryOut(
        cell_cents=cell,
        pack_cents=cell / share if share else cell,
        history=history,
        chemistries=[
            ChemistryOut(
                key=k,
                label=c.label,
                wh_per_kg=c.wh_per_kg,
                cost_mult=c.cost_mult,
                range_mult=c.range_mult,
            )
            for k, c in v.battery.chemistries.items()
        ],
        cell_makers=[
            CellMakerOut(
                key=m.key,
                name=m.name,
                country=m.country,
                price_mult=m.price_mult,
                share=_interp(m.share, at),
            )
            for m in v.cell_makers
        ],
    )


def _interp(points: dict[int, float], year: float) -> float:
    from tst.sim.vehicles.config import interp

    return interp(points, year)


def _price(state: GameState, product_id: int) -> int | None:
    for s in state.segments_of(product_id):
        if s.segment == "consumer" and s.price_cents is not None:
            return s.price_cents
    for rs in state.regional_segments_of(product_id):
        if rs.segment == "consumer" and rs.price_cents is not None:
            return rs.price_cents
    return None


def rivals_out(state: GameState, data: LoadedData) -> list[RivalCarOut]:
    b, d = data.balance, data.game_data
    home = home_region_of(state, b, d)
    cat = b.vehicles.category
    demand_by = {(home, m.segment): m.addressable for m in state.markets if m.category == cat}
    demand_by.update(
        {(m.region, m.segment): m.addressable for m in state.regional_markets if m.category == cat}
    )
    out = []
    for p in sorted(state.products, key=lambda p: p.id):
        if not is_vehicle(p, b) or rival_def(state, p, d) is None or p.status == "retired":
            continue
        company = state.company(p.company_id)
        assert company is not None
        shares = []
        for region in d.region_keys:
            mine = sum(
                s.customers
                for s in (state.segments_of(p.id) if region == home else ())
                if s.segment == "consumer"
            ) + sum(
                rs.customers
                for rs in state.regional_segments_of(p.id)
                if rs.region == region and rs.segment == "consumer"
            )
            total = demand_by.get((region, "consumer"), 0.0)
            if total > 0 and mine > 0:
                shares.append(RivalShareOut(region=region, share=mine / total))
        out.append(
            RivalCarOut(
                company_id=company.id,
                company=company.name,
                product=p.name,
                quality=p.quality,
                price_cents=_price(state, p.id),
                launched=_price(state, p.id) is not None,
                shares=shares,
            )
        )
    return out


def _regions_of(state: GameState, p: Product, home: str) -> list[tuple[str, int | None]]:
    return sales._regions_of(state, p.id, home)


def car_out(state: GameState, p: Product, data: LoadedData) -> MyCarOut:
    b, d = data.balance, data.game_data
    home = home_region_of(state, b, d)
    spec = vs.spec_of(state, p, d)
    capable = vs.capable_level(state, spec, p.company_id, b)
    cost = vs.unit_cost(state, p, b, d, capable)
    months = [m for m in state.vehicle_months if m.product_id == p.id]
    last = months[-1] if months else None
    regions = _regions_of(state, p, home)
    levels = [
        LevelRegionOut(
            region=r,
            level=vs.level_in(state, p, r, b, d, capable),
            approved=[
                k for k in LEVELS if k in b.vehicles.levels and vs.approved(state, r, k, b, d)
            ],
        )
        for r, _ in regions
    ]
    eligibility = []
    for r, price in regions:
        if not price:
            continue
        for title, amount, failed in subsidies.eligibility(state, p, r, price, b, d):
            eligibility.append(
                EligibilityOut(
                    region=r,
                    scheme=title,
                    amount_cents=amount,
                    eligible=not failed,
                    failed=list(failed),
                )
            )
    cars = sum(
        s.customers * d.category(p.category).market(s.segment).units_per_customer
        for s in state.segments_of(p.id)
    ) + sum(
        rs.customers * d.category(p.category).market(rs.segment).units_per_customer
        for rs in state.regional_segments_of(p.id)
    )
    software = sum(m.software_cents for m in months)
    unit_price = _price(state, p.id) or 0
    car_revenue = sum(m.units * unit_price for m in months)
    battery = last.battery_cents if last is not None else cost.battery
    lines = [
        CostLineOut(line="Battery pack", cents=battery),
        CostLineOut(line="Motors and power electronics", cents=cost.drive),
        CostLineOut(line="Chips", cents=cost.chips),
        CostLineOut(line="Body, chassis and interior", cents=cost.body),
        CostLineOut(line="Assembly", cents=last.assembly_cents if last is not None else 0.0),
    ]
    points = sales.feature_points(state, p.id, home, b, d) if regions else 0.0
    return MyCarOut(
        product_id=p.id,
        name=p.name,
        status=p.status,
        spec=VehicleSpecOut(
            pack_kwh=spec.pack_kwh,
            chemistry=spec.chemistry,
            charge_kw=spec.charge_kw,
            autonomy=spec.autonomy,
            platform=spec.platform,
            cells=spec.cells,
            os_product_id=spec.os_product_id,
        ),
        range_km=vs.range_km(spec, state.turn, b, d),
        level=last.level if last is not None else "none",
        capable_level=capable,
        customers=cars,
        units_last_month=last.units if last is not None else 0.0,
        price_cents=_price(state, p.id),
        unit_cost=lines,
        unit_cost_cents=sum(x.cents for x in lines),
        software_cents_last_month=last.software_cents if last is not None else 0,
        software_share=software / (software + car_revenue) if software + car_revenue > 0 else 0.0,
        feature_points=points,
        levels=levels,
        eligibility=eligibility,
        history=[
            CarMonthOut(
                turn=m.turn,
                units=m.units,
                software_cents=m.software_cents,
                licence_cents=m.licence_cents,
                unit_cost_cents=m.battery_cents
                + m.drive_cents
                + m.chips_cents
                + m.body_cents
                + m.assembly_cents,
            )
            for m in months
        ],
    )


def _status(state: GameState, ready_turn: int, closed: bool) -> str:
    if closed:
        return "closed"
    return "live" if state.turn >= ready_turn else "building"


def vehicles_out(state: GameState, data: LoadedData) -> VehiclesScreenOut:
    b, d = data.balance, data.game_data
    vb = b.vehicles
    group = group_ids(state)
    cars = [
        car_out(state, p, data)
        for p in sorted(state.products, key=lambda p: p.id)
        if p.company_id in group and is_vehicle(p, b) and p.status != "retired"
    ]
    market = cells.market_cents(state, b, d)
    cell_plants = []
    for cp in state.cell_plants:
        f = state.facility(cp.facility_id)
        if f is None or cp.company_id not in group:
            continue
        st = staffing(state, f, b)
        m = cp.month
        cell_plants.append(
            CellPlantOut(
                facility_id=f.id,
                name=facility_name(f, b, d),
                region=f.region,
                chemistry=cp.chemistry,
                capacity_mwh=f.capacity,
                status=_status(state, f.ready_turn, f.status == "closed"),
                ready=format_turn(f.ready_turn),
                estimate_cents=cp.estimate_cents,
                capex_paid_cents=f.capex_paid_cents,
                yield_rate=cp.yield_rate,
                made_kwh=m.made_kwh if m else 0.0,
                to_group_kwh=m.to_group if m else 0.0,
                to_spot_kwh=m.to_spot if m else 0.0,
                unit_cents=m.unit_cents if m else 0.0,
                market_cents=market,
                staff=st.staff,
                staff_needed=st.needed,
            )
        )
    plants = [
        VehiclePlantOut(
            facility_id=f.id,
            name=facility_name(f, b, d),
            region=f.region,
            cars_month=f.capacity,
            status=_status(state, f.ready_turn, f.status == "closed"),
            ready=format_turn(f.ready_turn),
            yield_rate=f.yield_rate,
            run_units=f.run_units,
        )
        for f in sorted(state.facilities, key=lambda f: f.id)
        if f.kind == vb.plant.kind and f.company_id in group
    ]
    networks = []
    for n in state.charging_networks:
        f = state.facility(n.facility_id)
        if f is None or n.company_id not in group:
            continue
        nm = n.month
        networks.append(
            ChargingOut(
                facility_id=f.id,
                name=facility_name(f, b, d),
                region=n.region,
                chargers=f.capacity,
                status=_status(state, f.ready_turn, f.status == "closed"),
                exclusive=n.exclusive,
                kwh_sold=nm.kwh_sold if nm else 0.0,
                revenue_cents=nm.revenue_cents if nm else 0,
                energy_cents=nm.energy_cents if nm else 0,
                use=nm.use if nm else 0.0,
            )
        )
    names = {p.id: p.name for p in state.products}
    incidents = [
        IncidentOut(
            turn=i.turn,
            when=format_turn(i.turn),
            product=names.get(i.product_id, f"product {i.product_id}"),
            region=i.region,
            level=i.level,
            cars_recalled=i.cars_recalled,
            cost_cents=i.cost_cents,
        )
        for i in state.incidents
        if i.company_id in group
    ]
    kinds = b.facility.kinds
    return VehiclesScreenOut(
        turn=state.turn,
        in_history=in_history(state.turn, b),
        scale_note=vb.scale_basis,
        regions=[region_out(state, r, data) for r in d.region_keys],
        battery=battery_out(state, data),
        rivals=rivals_out(state, data),
        cars=cars,
        vehicle_plants=plants,
        cell_plants=cell_plants,
        charging=networks,
        incidents=incidents,
        options=VehicleOptionsOut(
            chemistries=list(CHEMISTRIES),
            platforms=list(PLATFORM_CHOICES),
            levels=[
                LevelOptionOut(
                    key=k,
                    label=lv.label,
                    lead=lv.lead,
                    ai_quality=lv.ai_quality,
                    features=lv.features,
                    needs_approval=lv.approval,
                )
                for k, lv in vb.levels.items()
            ],
            cell_sources=list(cells.cell_sources(d)),
            cell_plant_sizes=list(kinds[vb.cell_plant.kind].sizes or ()),
            charging_sizes=list(kinds[vb.charging.kind].sizes or ()),
            vehicle_plant_sizes=list(kinds[vb.plant.kind].sizes or ()),
            pack_kwh=[vb.spec.pack_kwh.lo, vb.spec.pack_kwh.hi],
            charge_kw=[vb.spec.charge_kw.lo, vb.spec.charge_kw.hi],
            cell_plant_stage=vb.cell_plant.stage,
            autonomy_lead=state.research_lead(state.player.id, vb.domain),
        ),
    )
