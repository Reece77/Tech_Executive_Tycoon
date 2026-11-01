"""Offices, cities and product regions for the API (M9, formulas.md 19.7).

Display only: every number comes from the sim's formulas. Capacity and output stay hidden
(11.13): reach is shown as sellers counted by region and words.
"""

from __future__ import annotations

from tst.api.schemas.geo import (
    CityOut,
    GeoOut,
    LeasePreviewOut,
    OfficeOut,
    ProductRegionOut,
    ProductRegionsOut,
    RegionSegmentOut,
    TalentOut,
    TeamRegionOut,
    UnitRefOut,
)
from tst.loader import LoadedData
from tst.sim.actions.geo import default_regional_price, launch_problem, office_rent_cents
from tst.sim.calendar import format_turn
from tst.sim.errors import GeoRuleError, UnknownCityError, UnknownProductError
from tst.sim.geo import formulas as gf
from tst.sim.geo.cities import home_region, hq_city, person_work_city, unit_office_id
from tst.sim.geo.markets import reach_context
from tst.sim.geo.offices import crowded_people, flexible_seat_cents, office_members, office_of
from tst.sim.hiring.phases import employment_monthly_cost_cents
from tst.sim.org.rules import is_remote, org_view
from tst.sim.products.models import SELLING, Product
from tst.sim.products.phases import team_of
from tst.sim.state import GameState

EXAMPLE_ROLE, EXAMPLE_LEVEL = "software_engineer", "senior"  # the Lease dialog's example rate
HALF_POINT = 0.5  # one + mark per half attribute point of talent bonus (display only)


def _example_rate(city_key: str, data: LoadedData) -> int:
    band = data.game_data.role(EXAMPLE_ROLE).salary_band_mid_cents[EXAMPLE_LEVEL]
    return gf.city_market_mid_cents(band, data.game_data.city(city_key))


def _talent(city_key: str, data: LoadedData) -> list[TalentOut]:
    game = data.game_data
    labels = {s.key: s.label for s in game.skills}
    labels |= {"technical": "Technical", "business": "Business", "leadership": "Leadership"}
    return [
        TalentOut(label=labels.get(k, k), points=v, marks="+" * max(1, round(v / HALF_POINT)))
        for k, v in game.city(city_key).talent.items()
        if v > 0
    ]


def _units(state: GameState, office_id: int | None) -> list[UnitRefOut]:
    company = state.player.id
    return [
        UnitRefOut(unit_id=u.id, name=u.name)
        for u in state.active_units(company)
        if u.office_id == office_id and (office_id is not None or u.policy != "remote")
    ]


def geo_out(state: GameState, data: LoadedData) -> GeoOut:
    b, game = data.balance, data.game_data
    player = state.player
    hq = hq_city(player, b)
    members = office_members(state, player.id)
    crowded = crowded_people(state, player.id)
    staff = state.staff(player.id)
    people_in: dict[str, int] = {}
    for e in staff:
        city = person_work_city(state, state.person(e.person_id), b, game)
        people_in[city] = people_in.get(city, 0) + 1

    def head_cost(person_ids: list[int], rent: int) -> int | None:
        if not person_ids:
            return None
        pay = sum(
            employment_monthly_cost_cents(e, b, office_cents=0)
            for e in staff
            if e.person_id in person_ids
        )
        return round((pay + rent) / len(person_ids))

    flexible = [
        e.person_id for e in staff if not is_remote(state, e) and office_of(state, e) is None
    ]
    seat = flexible_seat_cents(state, player.id, b, game)
    offices = [
        OfficeOut(
            office_id=None,
            city=hq,
            city_label=game.city(hq).label + " (flexible HQ)",
            seats=None,
            people=len(flexible),
            monthly_rent_cents=seat * len(flexible),
            cost_per_head_cents=head_cost(flexible, seat * len(flexible)),
            units=[
                UnitRefOut(unit_id=u.id, name=u.name)
                for u in state.active_units(player.id)
                if unit_office_id(state, u.id) is None and u.policy != "remote"
            ],
            crowded=False,
            crowded_morale=None,
        )
    ]
    for office in state.company_offices(player.id):
        people = members.get(office.id, [])
        rent = office_rent_cents(office, b, game)
        is_crowded = any(p in crowded for p in people)
        offices.append(
            OfficeOut(
                office_id=office.id,
                city=office.city,
                city_label=game.city(office.city).label,
                seats=office.seats,
                people=len(people),
                monthly_rent_cents=rent,
                cost_per_head_cents=head_cost(people, rent),
                units=_units(state, office.id),
                crowded=is_crowded,
                crowded_morale=b.office.crowded_morale if is_crowded else None,
                opened=format_turn(office.opened_turn),
                close_penalty_cents=gf.close_penalty_cents(rent, b),
            )
        )
    return GeoOut(
        hq_city=hq,
        hq_label=game.city(hq).label,
        home_region=home_region(state, b, game),
        home_region_label=game.region(home_region(state, b, game)).label,
        offices=offices,
        cities=[
            CityOut(
                key=c.key,
                label=c.label,
                region=c.region,
                region_label=game.region(c.region).label,
                salary_index=c.salary_multiplier_bp / 10_000,
                rent_index=c.rent_index,
                talent=_talent(c.key, data),
                people=people_in.get(c.key, 0),
                is_hq=c.key == hq,
                seat_rent_cents=gf.lease_rent_cents(1, c.rent_index, b),
                example_rate_cents=_example_rate(c.key, data),
            )
            for c in game.cities
        ],
        seat_sizes=list(b.office.seat_sizes),
        lease_energy=b.office.lease_energy,
        close_energy=b.office.close_energy,
        assign_energy=b.office.assign_energy,
        close_penalty_months=b.office.close_penalty_months,
        relocation_cents=b.hiring.relocation_cents,
    )


def lease_preview(city: str, seats: int, data: LoadedData) -> LeasePreviewOut:
    b, game = data.balance, data.game_data
    if not game.has_city(city):
        raise UnknownCityError(f"unknown city {city!r}")
    if seats not in b.office.seat_sizes:
        raise GeoRuleError(f"an office has {', '.join(str(s) for s in b.office.seat_sizes)} seats")
    rent = gf.lease_rent_cents(seats, game.city(city).rent_index, b)
    return LeasePreviewOut(
        city=city,
        city_label=game.city(city).label,
        seats=seats,
        monthly_rent_cents=rent,
        fit_out_cents=gf.fit_out_cents(rent, b),
        example_rate_cents=_example_rate(city, data),
        energy=b.office.lease_energy,
    )


def _own_product(state: GameState, product_id: int) -> Product:
    product = state.product(product_id)
    if product is None or product.company_id != state.player.id:
        raise UnknownProductError(f"no product {product_id}")
    return product


def product_regions_out(state: GameState, product_id: int, data: LoadedData) -> ProductRegionsOut:
    b, game = data.balance, data.game_data
    product = _own_product(state, product_id)
    category = game.category(product.category)
    home = home_region(state, b, game)
    geo = reach_context(state, b, game)
    assert geo is not None
    team = team_of(state, org_view(state, state.player.id), product, b, game, estimate=True)
    sellers = [s.person_id for s in team.sellers]
    builders_by: dict[str, int] = {}
    for builder in team.builders:
        region = geo.regions_of.get(builder.person_id, home)
        builders_by[region] = builders_by.get(region, 0) + 1
    home_segments = state.segments_of(product.id)
    seg_keys = [s.segment for s in home_segments]
    rows: list[ProductRegionOut] = []
    for region in [home, *(r for r in game.region_keys if r != home)]:
        launch = state.product_region(product.id, region)
        if region == home:
            segs = [
                RegionSegmentOut(
                    segment=s.segment,
                    label=game.segment(s.segment).label,
                    price_cents=s.price_cents,
                    default_price_cents=category.market(s.segment).reference_price_cents,
                    customers=s.customers,
                    mrr_cents=round(s.customers * (s.price_cents or 0)),
                )
                for s in home_segments
            ]
            status, label = "home", "Home"
        else:
            segs = [
                RegionSegmentOut(
                    segment=s.segment,
                    label=game.segment(s.segment).label,
                    price_cents=s.price_cents,
                    default_price_cents=default_regional_price(
                        state, product.category, s.segment, region, b, game
                    ),
                    customers=s.customers,
                    mrr_cents=round(s.customers * (s.price_cents or 0)),
                )
                for s in state.regional_segments_of(product.id, region)
            ]
            if launch is None:
                status, label = "not_launched", "Not launched"
            elif launch.live(state.turn):
                status, label = "live", f"Live since {format_turn(launch.live_turn)}"
            else:
                status, label = "localizing", f"Localizing until {format_turn(launch.live_turn)}"
        neighbour = geo.neighbours[region]
        here = sum(1 for p in sellers if geo.regions_of.get(p) == region)
        near = sum(1 for p in sellers if geo.regions_of.get(p) == neighbour)
        present = region == home or region in geo.present
        reach_bits = []
        reach_bits.append(
            "Local presence: full awareness"
            if present
            else f"No local presence: self-serve awareness x {b.markets.foreign_awareness:g}"
        )
        if not here and not near:
            reach_bits.append("no sellers in or next to the region")
        addressable = 0.0
        for seg in seg_keys:
            if region == home:
                m = state.market(product.category, seg)
                addressable += m.addressable if m else 0.0
            else:
                rm = state.regional_market(product.category, seg, region)
                addressable += rm.addressable if rm else 0.0
        rivals = _rivals_in_region(state, product, region, home)
        problem = launch_problem(state, product.id, region, b, game) if region != home else None
        cost = gf.localization_cents(category.scope, b) if status == "not_launched" else None
        rows.append(
            ProductRegionOut(
                region=region,
                label=game.region(region).label,
                status=status,
                status_label=label,
                segments=segs,
                customers=sum(s.customers for s in segs),
                mrr_cents=sum(s.mrr_cents for s in segs),
                local_presence=present,
                sellers_here=here,
                sellers_neighbour=near,
                neighbour_label=game.region(neighbour).label,
                reach_note="; ".join(reach_bits),
                addressable=round(addressable),
                rivals=rivals,
                launch_cost_cents=cost,
                live_label=format_turn(state.turn + b.markets.localize_months)
                if status == "not_launched"
                else None,
                launch_problem=problem if status == "not_launched" else None,
            )
        )
    return ProductRegionsOut(
        product_id=product.id,
        name=product.name,
        regions=rows,
        team=[
            TeamRegionOut(region=r, label=game.region(r).label, builders=n)
            for r, n in sorted(builders_by.items(), key=lambda kv: game.region_index(kv[0]))
        ],
        time_zone_factor=team.region_factor,
        launch_energy=b.markets.launch_energy,
        localize_months=b.markets.localize_months,
    )


def _rivals_in_region(state: GameState, product: Product, region: str, home: str) -> int:
    """Other companies' products of the category selling in the region."""
    owners: set[int] = set()
    for other in state.products:
        if other.category != product.category or other.company_id == product.company_id:
            continue
        if other.status not in SELLING:
            continue
        if region == home:
            if state.segments_of(other.id):
                owners.add(other.id)
        else:
            launch = state.product_region(other.id, region)
            if launch is not None and launch.live(state.turn):
                owners.add(other.id)
    return len(owners)
