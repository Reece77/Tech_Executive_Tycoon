"""The Telecom screen's view (M53, docs/formulas.md 62): the player's networks, spectrum, auctions,
equipment and bans, from public figures and the player's own records. Hidden values (62.5): an
auction's rivals' values are never stored; a seeded auction, a seeded ban and 6G's month are shown
only once announced (or come); subscription growth after 2025 is never shown."""

from __future__ import annotations

from typing import Final

from tst.api.schemas.telecom import (
    AuctionOut,
    AwardOut,
    BanOut,
    CableOut,
    FibreOut,
    NetworkGenerationOut,
    SpectrumLicenceOut,
    LineOut,
    OperatorOut,
    NetworkPaybackOut,
    RadioOut,
    RegionNetworkOut,
    OperatorShareOut,
    TelecomScreenOut,
    VendorOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.geopolitics import world
from tst.sim.products.models import SELLING
from tst.sim.state import GameState
from tst.sim.telecom import equipment as eq
from tst.sim.telecom import networks as nw
from tst.sim.telecom import services
from tst.sim.telecom.actions import generation_open
from tst.sim.telecom.config import BanDef
from tst.sim.telecom.data import TINY, end_year_at, file, in_history, is_service
from tst.sim.telecom.models import SeededBan

YEAR_MONTHS: Final = 12  # tunable-exempt: calendar
TOP_RIVALS: Final = 4  # tunable-exempt: rivals shown a region


def _group(state: GameState) -> set[int]:
    return {c.id for c in world.group(state)}


def _generations(state: GameState, balance: Balance, data: GameData) -> list[NetworkGenerationOut]:
    out = []
    for g in file(data).generations:
        is_open = generation_open(state, g.key, data)
        first = g.first_turn if g.first_turn is not None else state.telecom.world.g6_turn
        points = balance.telecom.g6_feature_points if g.key == "g6" else g.feature_points
        out.append(
            NetworkGenerationOut(
                key=g.key,
                label=g.label,
                open=is_open,
                first=format_turn(first) if is_open and first is not None else None,
                feature_points=points,
            )
        )
    return out


def _rivals(
    state: GameState, region: str, home: str, balance: Balance, ids: set[int]
) -> list[OperatorShareOut]:
    by: dict[int, float] = {}
    for p in state.products:
        if p.category != balance.telecom.mobile or p.status not in SELLING or p.company_id in ids:
            continue
        n = services.customers_by_region(state, p, home).get(region, 0.0)
        if n > 0:
            by[p.company_id] = by.get(p.company_id, 0.0) + n
    total = sum(by.values())
    top = sorted(by.items(), key=lambda x: (-x[1], x[0]))[:TOP_RIVALS]
    return [
        OperatorShareOut(
            name=state.company(cid).name, subscribers=n, share=n / total if total > TINY else 0.0
        )
        for cid, n in top
    ]


def _regions(
    state: GameState, ids: set[int], balance: Balance, data: GameData
) -> list[RegionNetworkOut]:
    tb = balance.telecom
    home = home_region_of(state, balance, data)
    traffic = nw.traffic_gb(state, balance, data)
    market: dict[tuple[str, str], float] = {}
    for m in state.markets:
        market[(m.category, home)] = market.get((m.category, home), 0.0) + m.addressable
    for rm in state.regional_markets:
        key = (rm.category, rm.region)
        market[key] = market.get(key, 0.0) + rm.addressable
    out = []
    for region in data.region_keys:
        nets = [nw.network(state, c, region, balance, data) for c in sorted(ids)]
        mobile = sum(
            services.company_customers(state, c, tb.mobile, home).get(region, 0.0) for c in ids
        )
        fixed = sum(
            services.company_customers(state, c, tb.fixed, home).get(region, 0.0) for c in ids
        )
        whole = sum(
            services.company_customers(state, c, tb.wholesale, home).get(region, 0.0) for c in ids
        )
        best = max(nets, key=lambda n: (n.coverage, n.sites)) if nets else None
        capacity = sum(n.capacity_gb for n in nets)
        demand = mobile * traffic
        out.append(
            RegionNetworkOut(
                region=region,
                label=data.region(region).label,
                mobile_market=market.get((tb.mobile, region), 0.0),
                fixed_market=market.get((tb.fixed, region), 0.0),
                mobile_subscribers=mobile,
                fixed_subscribers=fixed,
                wholesale_contracts=whole,
                sites=sum(n.sites for n in nets),
                coverage=best.coverage if best else 0.0,
                coverage_by_generation=dict(best.generation_cov) if best else {},
                best_generation=(best.best or None) if best else None,
                capacity_gb=capacity,
                demand_gb=demand,
                quality=min(1.0, capacity / demand) if demand > TINY else 1.0,
                homes_passed=sum(n.homes_passed for n in nets),
                households=nw.households(state, region, balance, data),
                licensed=dict(best.licensed) if best else {},
                mhz=dict(best.mhz) if best else {},
                neutrality=services.neutrality_in_force(state, region, data),
                rivals=_rivals(state, region, home, balance, ids),
            )
        )
    return out


def _vendor_label(key: str, data: GameData) -> str:
    v = file(data).vendor(key)
    return "Your own" if key == "own" else (v.label if v else key)


def _radios(state: GameState, ids: set[int], data: GameData) -> list[RadioOut]:
    out = []
    for r in state.telecom.radios:
        f = state.facility(r.facility_id)
        if r.company_id not in ids or f is None:
            continue
        out.append(
            RadioOut(
                facility_id=r.facility_id,
                region=r.region,
                generation=r.generation,
                vendor=r.vendor,
                vendor_label=_vendor_label(r.vendor, data),
                overlay=r.overlay,
                sites=f.capacity,
                live_sites=f.live_capacity(state.turn),
                status=f.status,
                ready=format_turn(f.ready_turn),
                dark=r.dark,
                replaced=r.replaced,
                owed=eq.owed_sites(state, r, data),
                at_risk=eq.at_risk_sites(state, r, data),
                replacing=r.replaces_facility_id,
                capex_cents=f.capex_cents,
                capex_paid_cents=f.capex_paid_cents,
            )
        )
    return out


def _auctions(state: GameState, ids: set[int], data: GameData) -> list[AuctionOut]:
    f = file(data)
    out = []
    recent = state.turn - 3 * YEAR_MONTHS
    for a in state.telecom.auctions:
        if a.status == "closed" and a.turn < recent:
            continue
        area = f.region(a.region).area(a.area)
        mine = a.bid_company_id in ids
        out.append(
            AuctionOut(
                id=a.id,
                label=a.label,
                region=a.region,
                area=a.area,
                area_label=area.label if area else a.area,
                band=a.band,
                mhz=a.mhz,
                blocks=a.blocks,
                reserve_cents=a.reserve_cents,
                month=format_turn(a.turn),
                term_years=a.term_years,
                obligation=a.obligation,
                obligation_years=a.obligation_years,
                status="closed" if a.status == "closed" else "announced",
                biddable=a.status == "announced"
                and state.turn < a.turn
                and area is not None
                and area.method == "auction",
                my_blocks=a.bid_blocks if mine else 0,
                my_limit_cents=a.bid_limit_cents if mine else 0,
                rounds=a.rounds,
                price_cents=a.price_cents,
                awards=[
                    AwardOut(
                        bidder=w.bidder,
                        blocks=w.blocks,
                        paid_cents=w.paid_cents,
                        yours=w.company_id in ids,
                    )
                    for w in a.awards
                ],
            )
        )
    return sorted(out, key=lambda x: (x.status != "announced", x.id))


def _bans(state: GameState, data: GameData) -> list[BanOut]:
    out = []
    bans: list[BanDef | SeededBan] = [*file(data).bans, *state.telecom.world.bans]
    for b in bans:
        if state.turn < b.announced_turn:
            continue  # a ban is public from its announcement
        if isinstance(b, BanDef):
            out.append(
                BanOut(
                    label=b.label,
                    vendor=_vendor_label(b.vendor, data),
                    region=b.region,
                    area=b.area,
                    announced=format_turn(b.announced_turn),
                    no_new=format_turn(b.no_new_turn),
                    replace_by=format_turn(b.replace_turn) if b.replace_turn is not None else None,
                    scope=b.scope,
                )
            )
        else:
            assert isinstance(b, SeededBan)
            area = file(data).region(b.region).area(b.area)
            where = area.label if area else b.area
            out.append(
                BanOut(
                    label=f"{where}'s ban on {_vendor_label(b.vendor, data)}",
                    vendor=_vendor_label(b.vendor, data),
                    region=b.region,
                    area=b.area,
                    announced=format_turn(b.announced_turn),
                    no_new=format_turn(b.announced_turn),
                    replace_by=format_turn(b.replace_turn),
                    scope=1.0,
                )
            )
    return out


def payback_out(
    state: GameState, company_id: int, region: str, data: GameData
) -> NetworkPaybackOut | None:
    row = next((x for x in state.telecom.cash if x[0] == company_id and x[1] == region), None)
    if row is None:
        return None
    months = [m for m in state.telecom.months if m.company_id == company_id and m.region == region]
    last = months[-YEAR_MONTHS:]
    year = sum(m.cash_cents for m in last)
    to_go = None
    if row[2] < 0 and year > 0:
        to_go = -row[2] / (year / len(last))
    paid = next((t for c, r, t in state.telecom.paid_back if c == company_id and r == region), None)
    return NetworkPaybackOut(
        region=region,
        label=data.region(region).label,
        cash_cents=row[2],
        capex_cents=row[3],
        last_year_cash_cents=year,
        months_to_payback=to_go,
        paid_back=format_turn(paid) if paid is not None else None,
    )


def telecom_out(state: GameState, loaded: LoadedData) -> TelecomScreenOut:
    b, d = loaded.balance, loaded.game_data
    tb = b.telecom
    f = file(d)
    ids = _group(state)
    year = end_year_at(state.turn)
    player = state.player.id
    vendors = []
    for v in f.vendors:
        refused = [r for r in d.region_keys if eq.refusing_ban(state, r, v.key, b, d) is not None]
        vendors.append(
            VendorOut(
                key=v.key,
                label=v.label,
                price_mult=v.price_mult,
                world_share=v.share_at(year),
                radio_cents={
                    g.key: eq.radio_cents(state, player, g.key, v.key, b, d)
                    for g in f.generations
                    if generation_open(state, g.key, d)
                },
                refused_in=refused,
            )
        )
    lines = []
    for p in state.products:
        if p.company_id in ids and is_service(p, b) and p.status != "retired":
            s = state.telecom.setting(p.id)
            lines.append(
                LineOut(
                    product_id=p.id,
                    name=p.name,
                    category=p.category,
                    zero_rating=bool(s and s.zero_rating),
                    satellite_partner=bool(s and s.satellite_partner),
                )
            )
    payback = [
        x
        for c in sorted(ids)
        for r in d.region_keys
        if (x := payback_out(state, c, r, d)) is not None
    ]
    kinds = b.facility.kinds
    return TelecomScreenOut(
        month=format_turn(state.turn),
        history=in_history(state.turn, b),
        generations=_generations(state, b, d),
        regions=_regions(state, ids, b, d),
        radios=_radios(state, ids, d),
        fibres=[
            FibreOut(
                facility_id=x.facility_id,
                region=x.region,
                homes_thousands=fac.capacity,
                status=fac.status,
                ready=format_turn(fac.ready_turn),
                capex_cents=fac.capex_cents,
            )
            for x in state.telecom.fibres
            if x.company_id in ids and (fac := state.facility(x.facility_id)) is not None
        ],
        cables=[
            CableOut(
                facility_id=x.facility_id,
                name=x.name,
                regions=list(x.regions),
                km=x.km,
                tbps=fac.capacity,
                status=fac.status,
                ready=format_turn(fac.ready_turn),
                capex_cents=fac.capex_cents,
            )
            for x in state.telecom.cables
            if x.company_id in ids and (fac := state.facility(x.facility_id)) is not None
        ],
        licences=[
            SpectrumLicenceOut(
                id=x.id,
                region=x.region,
                area=x.area,
                area_label=(a.label if (a := f.region(x.region).area(x.area)) else x.area),
                band=x.band,
                mhz=x.mhz,
                paid_cents=x.paid_cents,
                book_cents=x.paid_cents - x.amortized_cents,
                since=format_turn(x.turn),
                expires=format_turn(x.expires_turn),
                obligation=x.obligation,
                obligation_due=format_turn(x.obligation_turn)
                if x.obligation_turn is not None
                else None,
                status=x.status,
                fines=x.fines,
            )
            for x in state.telecom.licences
            if x.company_id in ids
        ],
        auctions=_auctions(state, ids, d),
        vendors=vendors,
        bans=_bans(state, d),
        lines=lines,
        payback=payback,
        operators=[
            OperatorOut(
                name=o.company,
                region=o.region,
                mobile=o.mobile_at(year),
                fixed=o.fixed_at(year),
                supplier=_vendor_label(o.supplier, d) if o.supplier else None,
            )
            for o in f.operators
            if o.active(state.turn)
        ],
        site_civil_cents=eq.civil_cents(state, d),
        fibre_home_cents=f.fibre_home_at(year),
        cable_km_cents=f.cable_km_at(year),
        has_own_equipment=eq.own_line(state, player, b) is not None,
        sizes={k: list(kinds[k].sizes or b.facility.sizes) for k in tb.kinds},
    )
