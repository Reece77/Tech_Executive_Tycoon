"""The Fabs screen's and the node timeline's read model (M21, formulas.md 38). Fabs show their
quoted capex and what has been paid, never the facility's true capex with its hidden overrun;
staff show as counts and coverage, never skill; a future node shows its window until it
arrives, never its drawn month; rival foundries show what they have reached. Costs, prices and
yields are the engine's (sim.fabs)."""

from __future__ import annotations

from dataclasses import replace

from tst.api.schemas.fabs import (
    FabCustomerOut,
    FabHistoryOut,
    FabMonthOut,
    FabOut,
    FabQuoteOut,
    FabsOut,
    FoundryNodeOut,
    FoundryOut,
    NodeOut,
    NodesOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.chips import chips
from tst.sim.fabs import actions as fa
from tst.sim.fabs import formulas as fx
from tst.sim.fabs import market as fm
from tst.sim.fabs import nodes as nd
from tst.sim.fabs import supply as fs
from tst.sim.fabs.models import Fab, FabMonth
from tst.sim.fabs.plants import fab_name, is_live, materials_cents, node_label
from tst.sim.facilities import goods, lifecycle
from tst.sim.facilities.models import Facility
from tst.sim.state import GameState

MONTHS = 12
DIE_TYPE = "ai_accelerator"  # the Fabs screen prices a die as an AI accelerator (38.5 target 5)


def _label(turn: int | None) -> str | None:
    return format_turn(turn) if turn is not None and turn < nd.NEVER else None


def _die(
    state: GameState, fab: Fab, m: FabMonth, data: LoadedData
) -> tuple[float | None, float | None]:
    """An AI accelerator's cost per good die at the month's cost a start, and on a foundry slot
    at the node's market price (both at the company's design yield)."""
    b = data.balance
    if m.cost_per_start_cents <= 0 or m.market_cents <= 0:
        return None, None
    t = b.chips.types[DIE_TYPE]
    y = chips.chip_yield(state, fab.company_id, b, data.game_data)
    mature = b.fab.yield_.mature
    own = fx.die_cents(
        m.cost_per_start_cents, t.per_wafer, y, fab.yield_, mature, b.chips.packaging_cents
    )
    market = fx.die_cents(m.market_cents, t.per_wafer, y, mature, mature, b.chips.packaging_cents)
    return own, market


def _status(state: GameState, fab: Fab, f: Facility) -> str:
    turn = state.turn
    if f.status == "closed":
        return "closed"
    if fab.upgrading(turn):
        return "converting"
    if f.status == "building":
        if turn >= f.ordered_turn + fab.build_months and fab.tools > 0 and turn < fab.live_turn:
            return "waiting_tools"
        return "building"
    return "live" if is_live(fab, f, turn) else "building"


def fab_out(state: GameState, fab: Fab, f: Facility, data: LoadedData) -> FabOut:
    b, d = data.balance, data.game_data
    staffing = lifecycle.staffing(state, f, b)
    company = state.company(f.company_id)
    uq = fa.upgrade_quote(state, f.company_id, f.id, b, d) if f.status == "live" else None
    month = None
    m = fab.month
    if m is not None:
        own, market = _die(state, fab, m, data)
        month = FabMonthOut(
            turn=m.turn,
            available=m.available,
            own=m.own,
            sold=m.sold,
            utilization=m.utilization,
            **{"yield": m.yield_},
            reliability=m.reliability,
            depreciation_cents=m.depreciation_cents,
            fixed_cents=m.fixed_cents,
            materials_cents=m.materials_cents,
            power_cents=m.power_cents,
            staff_cents=m.staff_cents,
            revenue_cents=m.revenue_cents,
            slot_price_cents=m.slot_price_cents,
            market_cents=m.market_cents,
            cost_per_start_cents=m.cost_per_start_cents,
            die_cost_cents=own,
            die_market_cents=market,
        )
    supplied = [
        p.name
        for p in fs.chip_products(state, f.company_id, d)
        if any(s.facility_id == f.id for s in _shares_last(state, p.id, fab, data))
    ]
    return FabOut(
        id=f.id,
        company_id=f.company_id,
        company=company.name,
        name=fab_name(state, fab, b, d),
        node=fab.node,
        node_label=node_label(d, fab.node),
        duv=fab.duv,
        region=f.region,
        region_label=d.region(f.region).label,
        status=_status(state, fab, f),
        size=f.capacity,
        ready_turn=f.ready_turn,
        ready_label=format_turn(f.ready_turn),
        estimate_cents=fab.estimate_cents,
        capex_paid_cents=f.capex_paid_cents,
        book_value_cents=f.book_value_cents,
        tools=fab.tools,
        tools_label=_label(fab.tools_turn),
        staff=staffing.staff,
        staff_needed=staffing.needed,
        coverage=staffing.coverage,
        unit_id=f.unit_id,
        **{"yield": fab.yield_},
        months_run=fab.months_run,
        upgrade_node=fab.upgrade_node,
        upgrade_label=node_label(d, fab.upgrade_node) if fab.upgrade_node else None,
        upgrade_ready_label=_label(fab.upgrade_ready),
        next_node=uq.new if uq else None,
        upgrade_estimate_cents=uq.capex_cents if uq and uq.new else None,
        upgrade_allowed=bool(uq and uq.allowed),
        upgrade_reason=uq.reason if uq else "only a fab in production can convert",
        month=month,
        customers=[FabCustomerOut(name=n, starts=s) for n, s in (m.customers if m else ())],
        chips=supplied,
        history=[
            FabHistoryOut(
                turn=t,
                label=format_turn(t),
                **{"yield": y},
                utilization=u,
                cost_per_start_cents=c,
                market_cents=mk,
            )
            for t, y, u, c, mk in fab.history
        ],
    )


def _shares_last(
    state: GameState, product_id: int, fab: Fab, data: LoadedData
) -> list[fs.FabShare]:
    """The product's fab shares in the month just played (the fab's month)."""
    if fab.month is None:
        return []
    shown = replace(state, turn=fab.month.turn)
    product = shown.product(product_id)
    if product is None:
        return []
    return fs.product_shares(shown, product, data.balance, data.game_data)


def nodes_out(state: GameState, data: LoadedData) -> NodesOut:
    b, d = data.balance, data.game_data
    nf = fm.nodes_file(d)
    tl = fm.timeline(state, b, d)
    turn = state.turn
    names = {f.key: f.name for f in nf.foundries}
    nodes = []
    for key in nf.node_keys():
        hist = nf.node(key)
        fut = nf.future_node(key)
        arrived = tl.arrival[key] <= turn
        first = fm.public_arrival(state, key, b, d)
        reached = sorted(
            (
                FoundryNodeOut(foundry=f.key, name=names[f.key], turn=t, label=format_turn(t))
                for f in nf.foundries
                if (t := fm.public_reach(state, f.key, key, b, d)) is not None
            ),
            key=lambda r: r.turn,
        )
        nodes.append(
            NodeOut(
                key=key,
                label=node_label(d, key),
                generation=tl.generation(key),
                euv=fm.uses_euv(d, key, duv=False),
                duv_route=bool(hist and hist.duv_route),
                arrived=arrived,
                first_turn=first,
                first_label=_label(first),
                window_label=(
                    f"expected {fut.window[0][:4]}-{fut.window[1][:4]}"
                    if fut is not None and not arrived
                    else None
                ),
                reached=reached,
                market_cents=fm.node_price_cents(state, key, b, d) if arrived else None,
                capital_cents=tl.capital_cents[key] if arrived or hist is not None else None,
                need_level=fm.need_level(state, key, b, d),
                orderable=fm.orderable(state, key, b, d),
                tag=hist.tag if hist is not None else None,
            )
        )
    foundries = []
    for f in nf.foundries:
        got = tl.reached(f.key, turn)
        foundries.append(
            FoundryOut(
                key=f.key,
                name=f.name,
                region_label=d.region(f.region).label,
                newest=got[-1] if got else None,
                newest_label=node_label(d, got[-1]) if got else None,
                capacity_k=nd.capacity(tl, f, turn, b.fab),
                open_share=nd.open_share(f, turn),
                stopped=f.stops_at is not None and bool(got) and got[-1] == f.stops_at,
            )
        )
    leading = tl.leading(turn)
    median = fm.median_node(state, b, d)
    return NodesOut(
        turn=turn,
        leading=leading,
        leading_label=node_label(d, leading),
        median=median,
        median_label=node_label(d, median),
        price_factor=fm.price_factor(state, b, d),
        allocation_factor=fm.allocation_factor(state, b, d),
        nodes=nodes,
        foundries=foundries,
        euv_supplier=nf.euv.supplier,
        euv_tool_cents=fm.tool_price_cents(state, d),
        euv_short=goods.allocation_now(state, fm.EUV_GOOD, d) < 1,
    )


def fabs_out(state: GameState, data: LoadedData) -> FabsOut:
    b, d = data.balance, data.game_data
    player = state.player.id
    fabs = [
        fab_out(state, fab, f, data)
        for fab in state.fabs
        if (f := state.facility(fab.facility_id)) is not None and fab.company_id == player
    ]
    kind = b.facility.kinds["fab"]
    return FabsOut(
        fabs=fabs,
        timeline=nodes_out(state, data),
        process_level=fm.process_level(state, player, b, d),
        sizes=list(kind.sizes or ()),
        regions=list(d.region_keys),
        build_energy=b.fab.build_energy,
        upgrade_energy=b.fab.upgrade.energy,
    )


def quote_out(
    state: GameState, node: str, region: str, size: int, duv: bool, data: LoadedData
) -> FabQuoteOut:
    b, d = data.balance, data.game_data
    q = fa.quote(state, state.player.id, node, region, size, b, d, duv=duv)
    market = fm.node_price_cents(state, node, b, d) if fm.in_volume(state, node, b, d) else None
    life = b.facility.kinds["fab"].life_months
    starts = size
    dep = q.capex_cents / life
    fixed = q.capex_cents * b.fab.fixed_share / MONTHS
    probe = Fab(
        facility_id=0,
        company_id=state.player.id,
        node=node,
        estimate_cents=0,
        build_months=0,
        duv=duv,
    )
    materials = materials_cents(state, probe, b, d)
    per_start = (dep + fixed) / starts + materials
    return FabQuoteOut(
        node=node,
        node_label=node_label(d, node),
        region=region,
        size=size,
        duv=duv,
        euv=q.euv,
        capex_cents=q.capex_cents,
        monthly_capex_cents=q.monthly_capex_cents,
        build_months=q.build_months,
        tools=q.tools,
        tools_label=_label(q.tools_turn),
        ready_label=format_turn(q.ready_turn),
        staff_needed=q.staff_needed,
        need_level=q.need_level,
        level=q.level,
        allowed=q.allowed,
        reason=q.reason,
        market_cents=market,
        cost_per_start_cents=per_start,
    )
