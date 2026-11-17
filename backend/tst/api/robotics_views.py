"""Building the Robotics and Mobility API's responses (M39, docs/formulas.md 53.5) from the state:
published figures and the player's group's own books. A zone under review shows when it was
applied for, never its decision month; incidents once they have happened; rivals' public services
and lines. Nothing reads a draw, a seeded growth path or the home window."""

from __future__ import annotations

from typing import Final

from tst.api.schemas.robotics import (
    AnnouncementOut,
    AutomationMonthOut,
    RobotaxiCityOut,
    DepotOut,
    HistoryIncidentOut,
    HumanoidMarketOut,
    MobilityOptionsOut,
    MobilityScreenOut,
    PlantAutomationOut,
    ProductOptionOut,
    RivalServiceOut,
    RoboIncidentOut,
    RoboticsOptionsOut,
    RoboticsScreenOut,
    RobotLineOut,
    RobotMakerOut,
    RobotRegionOut,
    RobotShareOut,
    ServiceOut,
    UnitCostOut,
    YearPointOut,
    ZoneMonthOut,
    ZoneOut,
    ZoneSizeOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn, turn_to_ym
from tst.sim.facilities.compute import home_region_of
from tst.sim.facilities.lifecycle import facility_name
from tst.sim.group.assets import group_ids
from tst.sim.hardware.production import unit_bom_cents
from tst.sim.products.models import SELLING, Product
from tst.sim.robotics import automation, demand, humanoids
from tst.sim.robotics import robotaxi as rt
from tst.sim.robotics.data import era_turn, file, is_humanoid, is_industrial, is_mobility, year_at
from tst.sim.robotics.models import AutomationMonth, ZoneMonth
from tst.sim.state import GameState
from tst.sim.vehicles import spec as vs
from tst.sim.vehicles.config import interp

THOUSAND: Final = 1_000  # tunable-exempt: installations are thousands
VEHICLES: Final = "vehicles"  # tunable-exempt: categories.yaml key of M38's cars


def _month(turn: int) -> str:
    return format_turn(turn)


def _year_points(state: GameState, points: dict[int, float]) -> list[YearPointOut]:
    year = turn_to_ym(state.turn)[0]
    return [
        YearPointOut(year=y, value=v * THOUSAND) for y, v in sorted(points.items()) if y <= year
    ]


def regions_out(state: GameState, data: LoadedData) -> list[RobotRegionOut]:
    b, d = data.balance, data.game_data
    f = file(d)
    out = []
    for r in f.regions:
        real = demand.installations(state, r.key, b, d)
        year = turn_to_ym(state.turn)[0]
        dens = [v for y, v in sorted(r.density.items()) if y <= year]
        out.append(
            RobotRegionOut(
                region=r.key,
                label=d.region(r.key).label,
                installations_year=real,
                game_installations_year=real * b.robotics.scale,
                history=_year_points(state, r.installations),
                density=dens[-1] if dens else None,
                labour_cents_hour=r.labour_at(year),
                humanoid_adoption=demand.adoption_share(state, r.key, b),
            )
        )
    return out


def _price(state: GameState, product_id: int) -> int | None:
    for s in state.segments_of(product_id):
        if s.price_cents is not None:
            return s.price_cents
    for rs in state.regional_segments_of(product_id):
        if rs.price_cents is not None:
            return rs.price_cents
    return None


def makers_out(state: GameState, data: LoadedData) -> list[RobotMakerOut]:
    b, d = data.balance, data.game_data
    f = file(d)
    home = home_region_of(state, b, d)
    out = []
    for p in sorted(state.products, key=lambda p: p.id):
        if p.status == "retired" or not (is_industrial(p, b) or is_humanoid(p, b)):
            continue
        company = state.company(p.company_id)
        if company is None or company.is_player:
            continue
        maker = f.maker(company.name)
        hmaker = f.humanoid_maker(company.name)
        if maker is None and hmaker is None:
            continue
        served: dict[str, float] = {}
        mine: dict[str, float] = {}
        for q in state.products:
            if q.category != p.category:
                continue
            for s in state.segments_of(q.id):
                served[home] = served.get(home, 0.0) + s.customers
                if q.id == p.id:
                    mine[home] = mine.get(home, 0.0) + s.customers
            for rs in state.regional_segments_of(q.id):
                served[rs.region] = served.get(rs.region, 0.0) + rs.customers
                if q.id == p.id:
                    mine[rs.region] = mine.get(rs.region, 0.0) + rs.customers
        shares = [
            RobotShareOut(region=r, share=mine.get(r, 0.0) / served[r])
            for r in d.region_keys
            if served.get(r, 0.0) > 0 and mine.get(r, 0.0) > 0
        ]
        price = _price(state, p.id)
        out.append(
            RobotMakerOut(
                company_id=company.id,
                company=company.name,
                owner=(maker.owner if maker else hmaker.owner if hmaker else "") or "",
                product=p.name,
                category=p.category,
                quality=p.quality,
                price_cents=price,
                selling=price is not None,
                shares=shares,
            )
        )
    return out


def humanoids_out(state: GameState, data: LoadedData) -> HumanoidMarketOut:
    b, d = data.balance, data.game_data
    f = file(d)
    era_key = f.humanoids.era
    era = next(e for e in d.eras.eras if e.key == era_key)
    window = f"{era.window[0][0]}-{era.window[1][0]}" if era.window is not None else "historical"
    arrived = era_turn(state, d)
    home = state.robotics_world.home_turn
    return HumanoidMarketOut(
        era=era.label,
        window=window,
        arrived=_month(arrived) if arrived is not None else None,
        open=arrived is not None,
        homes_open=home is not None and state.turn >= home,
        actuator_index=humanoids.actuator_index(state, b),
        actuator_cents=humanoids.actuator_cents(state, b, d),
        best_capability=humanoids.best_capability(state, b, d),
        announcements=[
            AnnouncementOut(
                month=_month(a.turn),
                company=a.company,
                label=a.label,
                price_cents=round(a.price_cents) if a.price_cents is not None else None,
            )
            for a in f.humanoids.announcements
            if a.turn <= state.turn
        ],
    )


def _lines(state: GameState, data: LoadedData) -> list[RobotLineOut]:
    b, d = data.balance, data.game_data
    group = group_ids(state)
    out = []
    for p in sorted(state.products, key=lambda p: p.id):
        if p.company_id not in group or p.status == "retired":
            continue
        if not (is_industrial(p, b) or is_humanoid(p, b)):
            continue
        spec = state.humanoid_spec(p.id)
        human = is_humanoid(p, b)
        out.append(
            RobotLineOut(
                product_id=p.id,
                name=p.name,
                category=p.category,
                status=p.status,
                quality=p.quality,
                capability=humanoids.capability(state, p, b) if human else None,
                ai=("own" if spec and spec.ai_product_id else "licensed") if human else None,
                chips=("own" if spec and spec.chip_product_id else "bought") if human else None,
                customers=sum(s.customers for s in state.segments_of(p.id))
                + sum(rs.customers for rs in state.regional_segments_of(p.id)),
                unit_cost_cents=unit_bom_cents(state, p, b, d),
            )
        )
    return out


def _auto_month(m: AutomationMonth) -> AutomationMonthOut:
    return AutomationMonthOut(
        month=_month(m.turn),
        units=m.units,
        saved_cents=m.saved_cents,
        service_cents=m.service_cents,
        depreciation_cents=m.depreciation_cents,
        level=m.level,
    )


def _cost(report: dict[str, float]) -> UnitCostOut:
    total = report["labour"] + report["fixed"] + report["depreciation"] + report["robots"]
    return UnitCostOut(
        labour_cents=report["labour"],
        fixed_cents=report["fixed"],
        depreciation_cents=report["depreciation"],
        robots_cents=report["robots"],
        total_cents=total,
    )


def plants_out(state: GameState, data: LoadedData) -> list[PlantAutomationOut]:
    """Every live assembly or vehicle plant of the player's group, robots installed or not."""
    b, d = data.balance, data.game_data
    group = group_ids(state)
    out = []
    for f in sorted(state.facilities, key=lambda f: f.id):
        if f.company_id not in group or f.kind not in b.robotics.automation.plant_kinds:
            continue
        if f.status == "closed":
            continue
        a = state.plant_automation(f.id)
        robots = a.robots if a is not None else 0
        level = automation.level_of(f, robots, b)
        out.append(
            PlantAutomationOut(
                facility_id=f.id,
                name=facility_name(f, b, d),
                kind=f.kind,
                region=f.region,
                units_month=f.capacity,
                robots=robots,
                own_robots=a.own_robots if a is not None else 0,
                max_robots=automation.robots_for(f, b.robotics.automation.max_share, b),
                level=level,
                saving_cents=automation.saving_cents(state, f, level, b, d),
                wage_cents_month=automation.wage_month_cents(state, f.region, b, d),
                cost_without=_cost(automation.unit_cost_report(state, f, 0, b, d)),
                cost_with=_cost(automation.unit_cost_report(state, f, robots, b, d)),
                capex_cents=a.capex_cents if a is not None else 0,
                book_cents=(a.capex_cents - a.depreciated_cents) if a is not None else 0,
                month=_auto_month(a.month) if a is not None and a.month is not None else None,
                history=[_auto_month(m) for m in a.history] if a is not None else [],
            )
        )
    return out


def _options(state: GameState, data: LoadedData, category: str) -> list[ProductOptionOut]:
    group = group_ids(state)
    return [
        ProductOptionOut(product_id=p.id, name=p.name, quality=p.quality)
        for p in sorted(state.products, key=lambda p: p.id)
        if p.company_id in group and p.category == category and p.status == "live"
    ]


def robotics_out(state: GameState, data: LoadedData) -> RoboticsScreenOut:
    b, d = data.balance, data.game_data
    rb = b.robotics
    return RoboticsScreenOut(
        month=_month(state.turn),
        scale=rb.scale,
        scale_basis=rb.scale_basis,
        regions=regions_out(state, data),
        makers=makers_out(state, data),
        humanoids=humanoids_out(state, data),
        lines=_lines(state, data),
        plants=plants_out(state, data),
        options=RoboticsOptionsOut(
            robot_cents=automation.robot_price_cents(state, d),
            system_cents=automation.system_cents(state, d),
            service_share=file(d).prices.service_share,
            own_robot_lines=_options(state, data, rb.industrial),
            ai_models=_options(state, data, humanoids.AI_CATEGORY),
            accelerators=_options(state, data, humanoids.CHIP_CATEGORY),
            max_robots=rb.automation.max_robots,
            target_level=rb.automation.target_level,
        ),
    )


# --- Mobility ----------------------------------------------------------------------------------


def _zone_month(m: ZoneMonth, days: float) -> ZoneMonthOut:
    return ZoneMonthOut(
        month=_month(m.turn),
        cars=m.cars,
        rides=m.rides,
        utilisation=m.utilisation,
        revenue_cents=m.revenue_cents,
        energy_cents=m.energy_cents,
        cleaning_cents=m.cleaning_cents,
        insurance_cents=m.insurance_cents,
        remote_cents=m.remote_cents,
        depreciation_cents=m.depreciation_cents,
        contribution_cents=m.contribution_cents,
        contribution_per_ride_cents=m.contribution_cents / m.rides if m.rides > 0 else None,
        rides_per_car_day=m.rides / m.cars / days if m.cars > 0 else 0.0,
    )


def mobility_out(state: GameState, data: LoadedData) -> MobilityScreenOut:
    b, d = data.balance, data.game_data
    rb = b.robotics.robotaxi
    f = file(d).robotaxi
    group = group_ids(state)
    cities = []
    for c in f.cities:
        first = rt.first_service_turn(state, c.key, d)
        cities.append(
            RobotaxiCityOut(
                key=c.key,
                label=c.label,
                region=c.region,
                l4_approved=vs.approved(state, c.region, rt.L4, b, d),
                trips_month=rt.trips_month(state, c, b, d),
                fare_cents=c.fare_cents,
                acceptance=rt.acceptance(state, c.key, b, d),
                first_service=_month(first) if first is not None else None,
                rival_fleet=rt.rival_fleet(state, c.key, b, d),
            )
        )
    rivals = [
        RivalServiceOut(
            operator=r.operator,
            city=r.city,
            since=_month(r.since),
            running=r.running,
            fleet=r.fleet,
            rides_week=r.rides_week,
        )
        for r in rt.rival_services(state, b, d)
    ]
    history = [
        HistoryIncidentOut(month=i.month, operator=i.operator, city=i.city, label=i.label)
        for i in f.incidents
        if _turn(i.month) <= state.turn
    ]
    services = [
        ServiceOut(product_id=p.id, name=p.name, status=p.status, quality=p.quality, brand=p.brand)
        for p in sorted(state.products, key=lambda p: p.id)
        if p.company_id in group and is_mobility(p, b) and p.status != "retired"
    ]
    zones = []
    for z in sorted(state.zones, key=lambda z: z.id):
        if z.company_id not in group:
            continue
        c = rt.city(d, z.city)
        product = state.product(z.product_id)
        car = rt.car_cents_for_zone(state, z, b, d)
        months = [m for m in state.zone_months if m.zone_id == z.id]
        zones.append(
            ZoneOut(
                zone_id=z.id,
                product_id=z.product_id,
                service=product.name if product else "",
                city=z.city,
                city_label=c.label,
                size=z.size,
                status=z.status,
                applied=_month(z.applied_turn),
                approved=_month(z.approved_turn) if z.approved_turn is not None else None,
                suspended_until=_month(z.suspended_until)
                if z.status == "suspended" and z.suspended_until is not None
                else None,
                cars=z.cars,
                car_source="own" if z.car_product_id is not None else "bought",
                price_cents=z.price_cents or round(c.fare_cents),
                depot_cars=rt.depot_capacity(state, z.company_id, z.city, b),
                breakeven_rides=rt.breakeven_rides(c, b, car),
                month=_zone_month(z.month, rb.days_per_month) if z.month is not None else None,
                history=[_zone_month(m, rb.days_per_month) for m in months],
            )
        )
    depots = []
    for dp in state.depots:
        fac = state.facility(dp.facility_id)
        if fac is None or dp.company_id not in group:
            continue
        depots.append(
            DepotOut(
                facility_id=fac.id,
                name=facility_name(fac, b, d),
                city=dp.city,
                cars=fac.capacity,
                status=fac.status,
                ready=_month(fac.ready_turn),
            )
        )
    incidents = [
        RoboIncidentOut(
            month=_month(i.turn),
            zone_id=i.zone_id,
            city=i.city,
            serious=i.serious,
            cost_cents=i.cost_cents,
            suspended_until=_month(i.suspended_until) if i.suspended_until is not None else None,
        )
        for i in state.robo_incidents
        if i.company_id in group
    ]
    player = state.player.id
    level = b.vehicles.levels[rt.L4]
    depot_kind = b.facility.kinds[b.robotics.depot_kind]
    own_cars = []
    for p in sorted(state.products, key=lambda p: p.id):
        if p.company_id not in group or p.category != VEHICLES or p.status not in SELLING:
            continue
        spec = vs.spec_of(state, p, d)
        if vs.capable_level(state, spec, p.company_id, b) == rt.L4:
            own_cars.append(ProductOptionOut(product_id=p.id, name=p.name, quality=p.quality))
    return MobilityScreenOut(
        month=_month(state.turn),
        cities=cities,
        rivals=rivals,
        history_incidents=history,
        services=services,
        zones=zones,
        depots=depots,
        incidents=incidents,
        options=MobilityOptionsOut(
            can_drive_l4=rt.can_drive_l4(state, player, b),
            l4_lead=level.lead,
            l4_ai_quality=level.ai_quality,
            zone_sizes=[
                ZoneSizeOut(key=k, share=v.share, review_months=v.review_months)
                for k, v in rb.zone_sizes.items()
            ],
            robotaxi_cents=interp(f.vehicle_cents, year_at(state.turn)),
            own_car_lines=own_cars,
            depot_sizes=list(depot_kind.sizes or b.facility.sizes),
            depot_capex_cents=depot_kind.capex_per_unit_cents,
            max_cars=rb.max_cars,
        ),
    )


def _turn(month: str) -> int:
    from tst.sim.facilities.config import month_to_turn

    return month_to_turn(month)


def is_robot_line(p: Product, data: LoadedData) -> bool:
    return is_industrial(p, data.balance) or is_humanoid(p, data.balance)
