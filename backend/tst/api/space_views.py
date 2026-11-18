"""Building the Space API's responses (M40, docs/formulas.md 56.5) from the state: published figures
and the player's group's own records. A licence under review shows when it was applied for, never
its decision month; launches once flown; the debris rule and direct-to-device's opening once they
have come; rivals' public launches and constellations. Nothing reads a draw or a seeded path."""

from __future__ import annotations

from typing import Final

from tst.api.schemas.space import (
    BroadbandLineOut,
    ConstellationMonthOut,
    ConstellationOut,
    CostPerKgOut,
    FlightCostOut,
    LaunchOut,
    LineOptionOut,
    MilestoneOut,
    PaybackOut,
    ProviderOut,
    RegionServiceOut,
    ReuseLevelOut,
    RivalConstellationOut,
    ShellOut,
    SpaceLicenceOut,
    SpaceScreenOut,
    VehicleOut,
    WorldLaunchesOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn, turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.group.assets import group_ids
from tst.sim.products.models import Product
from tst.sim.space import constellation as con
from tst.sim.space import launch, policy, services
from tst.sim.space.config import REUSE_LEVELS
from tst.sim.space.data import LAST_YEAR, enabled, file, is_broadband, is_eo, is_launch, year_at
from tst.sim.space.models import Constellation
from tst.sim.state import GameState

RATE_BAND: Final = 0.3  # tunable-exempt: a shown failure chance is the model's +-30%
YEAR_MONTHS: Final = 12  # tunable-exempt: calendar


def flight_cost_out(state: GameState, product: Product, balance: Balance) -> FlightCostOut | None:
    spec = state.space.spec(product.id)
    if spec is None:
        return None
    level = launch.capable_level(state, spec, product.company_id, balance)
    c = launch.flight_cost(spec.payload_kg, product.quality, spec.flights, level, balance)
    e = launch.flight_cost(spec.payload_kg, product.quality, spec.flights, "expendable", balance)
    lv = balance.space.reuse[level]
    return FlightCostOut(
        level=level,
        build_cents=round(c.build_cents),
        reused_share=lv.reused_share,
        flights_per_vehicle=lv.flights,
        refurb_share=lv.refurb_share,
        operations_cents=round(launch.ops_cents(spec.payload_kg, balance)),
        flight_cents=round(c.flight_cents),
        payload_kg=c.payload_kg,
        cost_per_kg_cents=c.per_kg_cents,
        expendable_per_kg_cents=e.per_kg_cents,
    )


def _price(state: GameState, product: Product) -> int | None:
    return next(
        (
            s.price_cents
            for s in state.segments_of(product.id)
            if s.segment == "satellite_operators"
        ),
        None,
    )


def _vehicles(state: GameState, ids: set[int], balance: Balance) -> list[VehicleOut]:
    out = []
    for p in state.products:
        if p.company_id not in ids or not is_launch(p, balance) or p.status == "retired":
            continue
        spec = state.space.spec(p.id)
        cost = flight_cost_out(state, p, balance)
        if spec is None or cost is None:
            continue
        rate = launch.failure_rate(spec.flights, p.quality, balance)
        grounded = spec.grounded_until is not None and state.turn < spec.grounded_until
        pads = launch.site_capacity(state, p.company_id, balance)
        out.append(
            VehicleOut(
                product_id=p.id,
                name=p.name,
                status=p.status,
                quality=p.quality,
                payload_kg=spec.payload_kg,
                aim=spec.reuse,
                level=cost.level,
                cost=cost,
                price_cents=_price(state, p),
                flights=spec.flights,
                failures=spec.failures,
                reliability=(spec.flights - spec.failures) / spec.flights if spec.flights else None,
                failure_rate_lo=max(0.0, rate * (1 - RATE_BAND)),
                failure_rate_hi=min(1.0, rate * (1 + RATE_BAND)),
                grounded_until=format_turn(spec.grounded_until)
                if grounded and spec.grounded_until is not None
                else None,
                pads=pads,
                cadence=pads * balance.space.reuse[cost.level].pad_rate,
            )
        )
    return out


def payback_out(state: GameState, c: Constellation) -> PaybackOut:
    months = [m for m in state.space.months if m.constellation_id == c.id]
    last = months[-YEAR_MONTHS:]
    year = sum(m.cash_cents for m in last)
    to_go = None
    if c.cash_cents < 0 and year > 0:
        to_go = -c.cash_cents / (year / len(last))
    return PaybackOut(
        capex_cents=c.capex_cents,
        cash_cents=c.cash_cents,
        last_year_cash_cents=year,
        months_to_payback=to_go,
        paid_back=format_turn(c.paid_back_turn) if c.paid_back_turn is not None else None,
    )


def _constellations(
    state: GameState, ids: set[int], balance: Balance, data: GameData
) -> list[ConstellationOut]:
    cb = balance.space.constellation
    out = []
    for c in state.space.constellations:
        if c.company_id not in ids:
            continue
        product = state.product(c.product_id) if c.product_id is not None else None
        complete = set(con.complete_shells(c, balance))
        shells = [
            ShellOut(
                index=i,
                label=cb.shells[i].label if i < len(cb.shells) else f"Shell {i + 1}",
                satellites=c.in_shell(i),
                size=cb.shell_sats,
                complete=i in complete,
                regions=list(cb.shells[i].regions) if i < len(cb.shells) else [],
            )
            for i in range(c.shells)
        ]
        gbps, d2d = con.capacity_gbps(c, balance)
        history = [
            ConstellationMonthOut(
                month=format_turn(m.turn),
                in_orbit=m.in_orbit,
                subscribers=m.subscribers,
                revenue_cents=m.revenue_cents,
                spend_cents=m.spend_cents,
            )
            for m in state.space.months
            if m.constellation_id == c.id
        ]
        out.append(
            ConstellationOut(
                id=c.id,
                name=c.name,
                kind=c.kind,
                product_id=c.product_id,
                product=product.name if product else None,
                shells=shells,
                in_orbit=c.in_orbit(),
                ground=c.ground,
                planned=con.planned(c, balance),
                lost=c.lost,
                mass_kg=c.mass_kg,
                life_months=c.life_months,
                d2d=c.d2d,
                insured=c.insured,
                build_per_month=c.build_per_month,
                launches_per_month=c.launches_per_month,
                vehicle_product_id=c.vehicle_product_id,
                satellite_cents=round(con.satellite_cents(state, c, balance, data)),
                covered=list(con.covered_regions(c, balance)) if c.kind == "broadband" else [],
                capacity_gbps=gbps + d2d,
                payback=payback_out(state, c),
                history=history,
            )
        )
    return out


def _broadband(
    state: GameState, ids: set[int], player: int, balance: Balance, data: GameData
) -> list[BroadbandLineOut]:
    out = []
    unit = round(services.terminal_cents(state, balance, data))
    for p in state.products:
        if p.company_id not in ids or not is_broadband(p, balance) or p.status == "retired":
            continue
        covered = {r for c in services.serving(state, p) for r in con.covered_regions(c, balance)}
        cap, _ = services.capacity_by_region(state, p, balance, data)
        subs, d2d = services.customers_by_region(state, p, balance, data)
        regions = []
        for r in data.region_keys:
            lic = state.space.licence(p.company_id, r)
            regions.append(
                RegionServiceOut(
                    region=r,
                    label=data.region(r).label,
                    covered=r in covered,
                    licence=lic.status if lic else None,
                    subscribers=subs.get(r, 0.0),
                    serviceable=cap.get(r, 0.0),
                    d2d_subscribers=d2d.get(r, 0.0),
                )
            )
        out.append(
            BroadbandLineOut(
                product_id=p.id,
                name=p.name,
                status=p.status,
                terminal_price_cents=state.space.terminal_price(p.id) or 0,
                terminal_cost_cents=unit,
                d2d_partner=p.id in state.space.d2d_partners,
                d2d_capable=services.d2d_capable(state, p, data),
                regions=regions,
            )
        )
    return out


def space_out(state: GameState, loaded: LoadedData) -> SpaceScreenOut:
    b, d = loaded.balance, loaded.game_data
    month = format_turn(state.turn)
    if not enabled(state, b, d):
        return SpaceScreenOut(
            month=month,
            open=False,
            reusability_lead=0.0,
            programme_started=None,
            reuse_levels=[],
            vehicles=[],
            undesigned=[],
            eo_lines=[],
            launches=[],
            cost_per_kg=[],
            world_launches=[],
            providers=[],
            milestones=[],
            constellations=[],
            broadband=[],
            licences=[],
            rivals=[],
            d2d_open=None,
            debris_rule=None,
            site_regions=[],
            bought_launch_cents=0,
            bought_payload_kg=0.0,
        )
    f = file(d)
    player = state.player.id
    ids = group_ids(state)
    year = year_at(state.turn)
    now_year = turn_to_ym(state.turn)[0]
    lead = state.research_lead(player, b.space.domain)
    start = state.space.reuse_start(player)
    months = state.turn - start if start is not None else 0
    levels = [
        ReuseLevelOut(
            key=k,
            label=b.space.reuse[k].label,
            lead=b.space.reuse[k].lead,
            min_months=b.space.reuse[k].min_months,
            reached=lead >= b.space.reuse[k].lead and months >= b.space.reuse[k].min_months,
        )
        for k in REUSE_LEVELS
    ]
    names = {c.id: c.name for c in state.space.constellations}
    launches = [
        LaunchOut(
            month=format_turn(r.turn),
            vehicle=r.vehicle,
            purpose=r.purpose,
            constellation=names.get(r.constellation_id) if r.constellation_id else None,
            satellites=r.satellites,
            ok=r.ok,
            insured_cents=r.insured_cents,
        )
        for r in reversed(state.space.launches)
        if r.company_id in ids
    ]
    costs = [
        CostPerKgOut(
            vehicle=v.label,
            company=v.company,
            cost_per_kg_cents=v.cost_per_kg_at(min(year, LAST_YEAR + 0.99)),
            target=v.target,
        )
        for v in f.launch.vehicles
        if (v.first_turn <= state.turn and (v.retired_turn is None or state.turn <= v.retired_turn))
    ]
    world = [
        WorldLaunchesOut(year=y, launches=v)
        for y, v in sorted(f.launch.world.items())
        if y < now_year or (y == now_year and y <= LAST_YEAR)
    ]
    by_name = {c.name: c.id for c in state.companies}
    providers = [
        ProviderOut(
            company_id=by_name.get(p.company),
            company=p.company,
            launches_year=policy.rival_launches(state, d, p.company),
        )
        for p in f.launch.providers
        if p.first_turn is None or p.first_turn <= state.turn
    ]
    milestones = [
        MilestoneOut(month=format_turn(m.turn), label=m.label)
        for m in (*f.launch.milestones, *f.d2d.milestones)
        if m.turn <= state.turn
    ]
    licences = [
        SpaceLicenceOut(
            region=x.region,
            label=d.region(x.region).label,
            status=x.status,
            applied=format_turn(x.applied_turn),
            granted=format_turn(x.granted_turn) if x.granted_turn is not None else None,
        )
        for x in state.space.licences
        if x.company_id in ids
    ]
    rivals = [
        RivalConstellationOut(
            name=c.label,
            company=c.company,
            kind=c.kind,
            satellites=policy.rival_satellites(state, d, c.key),
            subscribers=c.subscribers_at(min(year, LAST_YEAR + 0.99)) if c.subscribers else None,
        )
        for c in f.constellations
        if c.first_turn <= state.turn
    ]
    debris = state.space.world.debris_turn
    price, payload = launch.bought_price_cents(state, b, d)
    return SpaceScreenOut(
        month=month,
        open=True,
        reusability_lead=lead,
        programme_started=format_turn(start) if start is not None else None,
        reuse_levels=levels,
        vehicles=_vehicles(state, ids, b),
        undesigned=[
            LineOptionOut(product_id=p.id, name=p.name)
            for p in state.products
            if p.company_id in ids
            and is_launch(p, b)
            and p.status != "retired"
            and state.space.spec(p.id) is None
        ],
        eo_lines=[
            LineOptionOut(product_id=p.id, name=p.name)
            for p in state.products
            if p.company_id in ids and is_eo(p, b) and p.status != "retired"
        ],
        launches=launches,
        cost_per_kg=costs,
        world_launches=world,
        providers=providers,
        milestones=milestones,
        constellations=_constellations(state, ids, b, d),
        broadband=_broadband(state, ids, player, b, d),
        licences=licences,
        rivals=rivals,
        d2d_open=format_turn(f.d2d.open_turn) if state.turn >= f.d2d.open_turn else None,
        debris_rule=format_turn(debris) if debris is not None and state.turn >= debris else None,
        site_regions=list(b.space.site_regions),
        bought_launch_cents=round(price),
        bought_payload_kg=payload,
    )
