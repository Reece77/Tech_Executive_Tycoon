"""The Infrastructure screen for the API (M12a, formulas.md 22.6).

Display only: every number comes from the sim's formulas. Component indexes are shown for
months up to the one the player is in, never later; reliability is shown but never the
staff's skills behind it (ADR-0007).
"""

from __future__ import annotations

from collections.abc import Mapping

from tst.api.schemas.facilities import (
    BuildPreviewOut,
    CloudOut,
    CloudSegmentOut,
    ComponentOut,
    ContractOut,
    FacilityOut,
    IndexPointOut,
    InfrastructureOut,
    KindOut,
    OutageOut,
    RegionOptionOut,
    SpotOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.commodities import power
from tst.sim.facilities import compute, goods, lifecycle
from tst.sim.facilities import formulas as ff
from tst.sim.facilities.models import Facility, GoodMonth
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.money import exact
from tst.sim.products.models import SELLING
from tst.sim.state import GameState

MONTHS_PER_YEAR = 12
OUTAGE_WINDOW = 12  # months of outages counted on the Cloud hosting panel (wireframe)

type Stored = Mapping[tuple[str, int], GoodMonth]


def current_turn(state: GameState, data: LoadedData) -> int:
    """The latest month the player may see an index for (22.6): the month being played
    while there is history, then the last month played, never later, whatever was loaded
    (M12r)."""
    components = data.game_data.components
    assert components is not None
    if state.turn <= components.last_turn:
        return state.turn
    latest = [g.turn for g in state.supply]
    return min([*latest, state.turn - 1]) if latest else components.last_turn


def month_at(
    good: str, turn: int, state: GameState, data: LoadedData, stored: Stored
) -> GoodMonth | None:
    """A good's month from history or from the months already played, never ahead."""
    components = data.game_data.components
    assert components is not None
    if turn > current_turn(state, data) or turn < 0:
        return None
    known = goods.history_month(components.good(good), turn)
    if known is not None:
        return known
    return stored.get((good, turn)) or next(
        (g for g in state.supply if g.good == good and g.turn == turn), None
    )


def _note(month: GoodMonth, turn: int, label: str) -> str:
    if month.allocation < 1:
        return f"{label} are short: {month.allocation:.0%} allocation"
    if month.in_shock(turn):
        return "A supply shock is running"
    return "Full allocation"


def components_out(state: GameState, data: LoadedData, stored: Stored) -> list[ComponentOut]:
    components = data.game_data.components
    assert components is not None
    now = current_turn(state, data)
    window = data.balance.supply.history_months
    out = []
    for good in components.goods:
        month = month_at(good.key, now, state, data, stored) or goods.current(
            state, good.key, data.game_data
        )
        year_ago = month_at(good.key, max(0, now - MONTHS_PER_YEAR), state, data, stored)
        change = month.index / year_ago.index - 1 if year_ago and now >= MONTHS_PER_YEAR else 0.0
        history = []
        for t in range(max(0, now - window), now + 1):
            m = month_at(good.key, t, state, data, stored)
            if m is not None:
                history.append(
                    IndexPointOut(
                        turn=t, label=format_turn(t), index=m.index, allocation=m.allocation
                    )
                )
        out.append(
            ComponentOut(
                good=good.key,
                label=good.label,
                index=month.index,
                change_12m=change,
                allocation=month.allocation,
                note=_note(month, now, good.label),
                history=history,
            )
        )
    return out


def spot_out(state: GameState, data: LoadedData) -> list[SpotOut]:
    b, d = data.balance, data.game_data
    out = []
    for key, spec in b.compute.goods.items():
        cents = compute.spot_unit_cents(state, key, b, d)
        out.append(
            SpotOut(
                good=key,
                label=spec.label,
                cents_per_unit=round(cents),
                index=cents / spec.spot_cents,
            )
        )
    return out


def _monthly_cost(state: GameState, facility: Facility, data: LoadedData) -> int:
    turn = state.turn
    kind = data.balance.facility.kinds[facility.kind]
    dep = ff.cumulative_depreciation_cents(
        facility.capex_cents,
        facility.capacity,
        facility.on_time,
        facility.ready_turn,
        facility.late_turn,
        kind.life_months,
        turn,
    ) - ff.cumulative_depreciation_cents(
        facility.capex_cents,
        facility.capacity,
        facility.on_time,
        facility.ready_turn,
        facility.late_turn,
        kind.life_months,
        turn - 1,
    )
    return dep + power.operating_cents(state, facility, data.balance, data.game_data)


def facility_out(
    state: GameState, facility: Facility, alloc: compute.Allocation, data: LoadedData
) -> FacilityOut:
    b, d = data.balance, data.game_data
    kind = b.facility.kinds[facility.kind]
    turn = state.turn
    live = facility.live_capacity(turn)
    own, sold = alloc.own.get(facility.id, 0.0), alloc.sold.get(facility.id, 0.0)
    staffing = lifecycle.staffing(state, facility, b)
    cost = _monthly_cost(state, facility, data)
    used = own + sold
    building = turn < facility.ready_turn
    unit = state.unit(facility.unit_id) if facility.unit_id is not None else None
    late = facility.capacity - facility.on_time
    return FacilityOut(
        facility_id=facility.id,
        name=lifecycle.facility_name(facility, b, d),
        kind=facility.kind,
        kind_label=kind.label,
        region=facility.region,
        region_label=d.region(facility.region).label,
        unit=kind.unit,
        status="building"
        if building
        else facility.status
        if facility.status != "building"
        else "live",
        since=format_turn(facility.ordered_turn if building else facility.ready_turn),
        units=facility.capacity,
        live_units=live,
        own_use=own,
        sold_use=sold,
        free=max(0.0, live - used),
        utilization=used / live if live else 0.0,
        reliability=None if building else staffing.reliability,
        staff=staffing.staff,
        staff_needed=staffing.needed,
        coverage=staffing.coverage,
        unit_id=facility.unit_id,
        unit_name=unit.name if unit else None,
        monthly_cost_cents=cost,
        power_index=power.kind_index(state, facility.kind, facility.region, b, d),
        cost_per_used_cents=round(cost / used) if used > 0 and not building else None,
        spot_cents=round(compute.spot_unit_cents(state, kind.output_good, b, d)),
        book_value_cents=facility.book_value_cents,
        capex_cents=facility.capex_cents,
        capex_paid_cents=facility.capex_paid_cents,
        build_progress=(turn - facility.ordered_turn) / kind.build_months if building else None,
        ready=format_turn(facility.ready_turn),
        late_units=late,
        late_ready=format_turn(facility.late_turn) if late else None,
        sale_value_cents=round(exact(facility.book_value_cents) * exact(b.facility.sale_share)),
    )


def contracts_out(state: GameState, data: LoadedData, company_id: int) -> list[ContractOut]:
    components = data.game_data.components
    assert components is not None
    tp = data.balance.supply.take_or_pay
    return [
        ContractOut(
            contract_id=c.id,
            good=c.good,
            good_label=components.good(c.good).label,
            index=c.index,
            signed=format_turn(c.signed_turn),
            ends=format_turn(c.end_turn),
            volume=c.volume,
            used=c.used,
            status=c.status,
            take_or_pay_cents=round(c.remaining * exact(c.unit_value_cents) * exact(tp)),
            settled_cents=c.settled_cents,
        )
        for c in sorted(state.company_contracts(company_id), key=lambda c: -c.id)
    ]


def _price_per_unit(rows: list[tuple[float, float, int | None]]) -> int | None:
    """Customers-weighted price per CU over (customers, units per customer, price) rows."""
    units = sum(c * u for c, u, p in rows if p is not None)
    if units <= 0:
        priced = [(p / u) for _, u, p in rows if p is not None]
        return round(sum(priced) / len(priced)) if priced else None
    return round(sum(c * (p or 0) for c, _, p in rows) / units)


def cloud_out(
    state: GameState, alloc: compute.Allocation, data: LoadedData, company: int
) -> CloudOut:
    b, d = data.balance, data.game_data
    category = d.category(b.compute.capacity_category)
    units = {m.segment: m.units_per_customer for m in category.markets}
    product = compute.capacity_product(state, company, d)
    segments: list[CloudSegmentOut] = []
    revenue = 0
    if product is not None:
        rows = list(state.segments_of(product.id))
        for seg in rows:
            regional = [
                r for r in state.regional_segments_of(product.id) if r.segment == seg.segment
            ]
            customers = seg.customers + sum(r.customers for r in regional)
            revenue += round(seg.customers * (seg.price_cents or 0))
            revenue += sum(round(r.customers * (r.price_cents or 0)) for r in regional)
            segments.append(
                CloudSegmentOut(
                    segment=seg.segment,
                    label=d.segment(seg.segment).label,
                    customers=customers,
                    units=customers * units[seg.segment],
                    price_cents=seg.price_cents,
                    price_per_unit_cents=(
                        round(seg.price_cents / units[seg.segment]) if seg.price_cents else None
                    ),
                )
            )
    mine = [(s.customers, units[s.segment], s.price_cents) for s in segments]
    leader = None
    best = 0.0
    for p in state.products:
        if p.category != category.key or p.company_id == company or p.status not in SELLING:
            continue
        total = sum(s.customers for s in state.segments_of(p.id))
        if total > best:
            best, leader = total, p
    leader_rows = (
        [(s.customers, units[s.segment], s.price_cents) for s in state.segments_of(leader.id)]
        if leader
        else []
    )
    outages = [o for o in state.outages if o.company_id == company]
    recent = [o for o in outages if o.turn > state.turn - 1 - OUTAGE_WINDOW]
    spare = (
        compute.spare_by_region(state, company, b, d)
        if any(compute.is_compute(f, b) for f in state.company_facilities(company))
        else {}
    )
    home = compute.home_region_of(state, b, d)
    names = {f.id: lifecycle.facility_name(f, b, d) for f in state.facilities}
    return CloudOut(
        product_id=product.id if product else None,
        product_name=product.name if product else None,
        selling=product is not None and product.status in SELLING,
        can_start=product is None
        and any(compute.is_compute(f, b) for f in state.company_facilities(company)),
        segments=segments,
        customers=sum(s.customers for s in segments),
        units_sold=sum(s.units for s in segments),
        revenue_cents=revenue,
        spare_units=max(0.0, spare.get(home, 0.0) - sum(s.units for s in segments)),
        price_per_unit_cents=_price_per_unit(mine),
        leader_name=state.company(leader.company_id).name if leader else None,
        leader_price_per_unit_cents=_price_per_unit(leader_rows) if leader else None,
        outages_12m=len(recent),
        outages=[
            OutageOut(
                turn=o.turn,
                label=format_turn(o.turn),
                facility=names.get(o.facility_id, f"#{o.facility_id}"),
                customers_lost=o.customers_lost,
            )
            for o in sorted(outages, key=lambda o: -o.id)
        ],
    )


def infrastructure_out(
    state: GameState, data: LoadedData, stored: Stored, company: int
) -> InfrastructureOut:
    """The Infrastructure screen of one company (ADR-0020 1): the route resolves which
    (M12r)."""
    b, d = data.balance, data.game_data
    alloc = compute.allocate(state, company, b, d)
    facilities = [
        facility_out(state, f, alloc, data)
        for f in sorted(state.company_facilities(company), key=lambda f: f.id)
        if compute.is_compute(f, b)  # M12b: plants are on the Hardware screen
    ]
    general = b.facility.kinds[next(iter(b.facility.kinds))]
    full = general.capex_per_unit_cents / general.life_months + general.opex_per_unit_cents
    home = compute.home_region_of(state, b, d)
    return InfrastructureOut(
        turn_label=format_turn(state.turn),
        components=components_out(state, data, stored),
        spot=spot_out(state, data),
        facilities=facilities,
        total_live_units=sum(f.live_units for f in facilities),
        total_building_units=sum(f.units - f.live_units for f in facilities),
        contracts=contracts_out(state, data, company),
        cloud=cloud_out(state, alloc, data, company),
        kinds=[
            KindOut(
                key=key,
                label=k.label,
                unit=k.unit,
                input_good=k.input_good,
                build_months=k.build_months,
                life_months=k.life_months,
                opex_per_unit_cents=k.opex_per_unit_cents,
                capex_per_unit_cents=ff.capex_cents(
                    1, k.capex_per_unit_cents, goods.index_now(state, k.input_good, d)
                ),
            )
            for key, k in b.facility.kinds.items()
            if k.output_good in b.compute.goods  # data centres only (M12b)
        ],
        sizes=list(b.facility.sizes),
        regions=[
            RegionOptionOut(key=r.key, label=r.label, is_home=r.key == home) for r in d.regions
        ],
        build_energy=b.facility.build_energy,
        sell_energy=b.facility.close_energy,
        contract_energy=b.supply.contract_energy,
        staff_energy=b.facility.assign_energy,
        contract_months=[int(b.supply.contract_months.lo), int(b.supply.contract_months.hi)],
        take_or_pay=b.supply.take_or_pay,
        sale_share=b.facility.sale_share,
        break_even_utilization=full / b.compute.goods[b.compute.plain_good].spot_cents,
    )


def build_preview(
    state: GameState,
    kind: str,
    region: str,
    capacity: int,
    contract_id: int | None,
    balances: LedgerBalances,
    data: LoadedData,
    company: int,
) -> BuildPreviewOut:
    b, d = data.balance, data.game_data
    q = lifecycle.quote(state, company, kind, region, capacity, b, d, contract_id)
    k = b.facility.kinds[kind]
    power_index = power.kind_index(state, kind, region, b, d)  # M17 (33.5)
    opex = round(power.opex_cents(k.opex_per_unit_cents, power_index))
    full = ff.monthly_cost_cents(capacity, q.capex_cents, k.life_months, opex)
    return BuildPreviewOut(
        power_index=power_index,
        kind=kind,
        region=region,
        units=capacity,
        index=q.index,
        capex_cents=q.capex_cents,
        monthly_capex_cents=q.monthly_capex_cents,
        build_months=q.build_months,
        ready=format_turn(state.turn + q.build_months),
        allocation=q.allocation,
        on_time=q.on_time,
        late=q.late,
        late_months=q.late_months,
        staff_needed=q.staff_needed,
        contract_id=q.contract_id,
        contracted=q.contracted,
        monthly_cost_full_cents=full,
        cost_per_unit_full_cents=round(full / capacity),
        spot_cents=round(compute.spot_unit_cents(state, k.output_good, b, d)),
        energy=b.facility.build_energy,
        can_afford=account_balance(balances, company, CASH) >= q.monthly_capex_cents,
    )
