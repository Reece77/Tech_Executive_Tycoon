"""The Equipment screen's data (M33, docs/formulas.md 47.6). Public facts only: generations,
published prices and throughput, the player's orders with their place as a lead-time range,
deliveries, stock, controls once announced, and the programme's public estimates. Never an
allocation weight or jitter, a programme's work, overrun or success draw, or a capacity before
ASML's December announcement."""

from __future__ import annotations

from typing import Final

from tst.api.schemas.equipment import (
    EquipmentOut,
    LithoProgrammeOut,
    LithoStageOut,
    OwnToolsOut,
    ToolControlOut,
    ToolGenerationOut,
    ToolOrderOut,
    ToolShipmentOut,
    ToolStockOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn, turn_to_ym
from tst.sim.equipment import data as ed
from tst.sim.equipment import programme as ep
from tst.sim.equipment import queue as eq
from tst.sim.equipment import stock
from tst.sim.equipment.actions import lead_text
from tst.sim.equipment.config import MONTHS, GenerationDef, ProgrammeDef
from tst.sim.equipment.controls import EUV
from tst.sim.equipment.fablink import ToolPlan, prepay_cents
from tst.sim.equipment.models import Programme
from tst.sim.fabs import market as fm
from tst.sim.geopolitics import rules as gr
from tst.sim.geopolitics import world
from tst.sim.modes.models import world_start_turn
from tst.sim.state import GameState

THIN, DEEP = 0.75, 1.25  # tunable-exempt: book labels (open orders / next year's capacity)
NOTE: Final = (
    "ASML is the only maker of EUV tools. Orders join its queue; each quarter's tools go to "
    "open orders in queue order, a long-standing customer's orders and prepaid ones moving up. "
    "Your place shows as a range of months to your last tool."
)


def _group(state: GameState, data: LoadedData) -> set[int]:
    if world.enabled(data.game_data):
        return {c.id for c in world.group(state)}
    return {state.player.id}


def _node_label(data: LoadedData, node: str) -> str:
    nf = data.game_data.nodes
    if nf is None:
        return node
    n = nf.node(node)
    if n is not None:
        return n.label
    f = nf.future_node(node)
    return f.label if f is not None else node


def _book(state: GameState, g: GenerationDef) -> str:
    nxt = max(1, ed.capacity(state, g, ed.year_of(state.turn) + 1))
    depth = ed.open_tools(state, g.key) / nxt
    if depth < THIN:
        return "thin"
    return "a year deep" if depth <= DEEP else "long"


def generations_out(state: GameState, data: LoadedData) -> list[ToolGenerationOut]:
    ef = ed.equipment_file(data.game_data)
    b = data.balance
    year = ed.year_of(state.turn)
    out = []
    for g in ef.generations:
        m = g.model_in(year)
        nxt = year + 1
        announced = nxt <= g.last_year or ed.supplier_year(state, g.key, nxt) is not None
        cap_next = ed.capacity(state, g, nxt) if announced and nxt <= year + 1 else None
        if nxt > g.last_year and ed.supplier_year(state, g.key, nxt) is None:
            cap_next = None  # not announced before its December
        out.append(
            ToolGenerationOut(
                key=g.key,
                label=g.label,
                maker=ef.supplier(g.maker).name,
                queued=g.queued,
                nodes=list(g.nodes),
                node_labels=[_node_label(data, n) for n in g.nodes],
                first_shipment_label=format_turn(g.first_shipment_turn),
                first_volume_label=format_turn(g.first_volume_turn),
                model=m.model,
                wph=m.wph,
                uptime=round(ed.uptime(g, state.turn), 3),
                price_cents=ed.price_cents(state, g, b),
                list_cents=round(ed.base_price_cents(g, state.turn, b.equipment.price.growth)),
                shipments=[
                    ToolShipmentOut(year=y, tools=ed.capacity(state, g, y))
                    for y in range(max(turn_to_ym(world_start_turn(state.mode))[0], year - 9), year)
                    if y >= ed.year_of(g.first_shipment_turn)
                ],
                capacity_next=cap_next,
                book=_book(state, g) if g.queued else "not queued",
                shipping=state.turn >= g.first_shipment_turn,
            )
        )
    return out


def orders_out(state: GameState, data: LoadedData) -> list[ToolOrderOut]:
    from tst.sim.fabs.plants import fab_name

    group = _group(state, data)
    ef = ed.equipment_file(data.game_data)
    out = []
    for o in state.tool_orders:
        if o.buyer != eq.PLAYER or o.company_id not in group or o.status == "cancelled":
            continue
        low = high = None
        if o.status == "open":
            lead = eq.lead(state, o, data.balance, data.game_data)
            low, high = lead.low, lead.high
        fab = fm.fab_of(state, o.facility_id) if o.facility_id is not None else None
        plan = ToolPlan(
            o.generation,
            o.remaining,
            0,
            0,
            o.remaining,
            o.price_cents,
            o.price_cents,
            None,
            None,
            None,
            None,
        )
        out.append(
            ToolOrderOut(
                id=o.id,
                generation=o.generation,
                generation_label=ef.generation(o.generation).label,
                tools=o.tools,
                delivered=o.delivered,
                placed_label=format_turn(o.placed_turn),
                status=o.status,
                prepaid=o.prepaid,
                price_cents=o.price_cents,
                fab_id=o.facility_id,
                fab=fab_name(state, fab, data.balance, data.game_data) if fab else None,
                lead_low=low,
                lead_high=high,
                lead_label=lead_text(eq.Lead(low, high)) if o.status == "open" else o.status,
                prepay_cents=(
                    prepay_cents(plan, data.balance)
                    if o.status == "open" and not o.prepaid
                    else None
                ),
            )
        )
    return out


def stock_out(state: GameState, data: LoadedData) -> list[ToolStockOut]:
    group = _group(state, data)
    ef = ed.equipment_file(data.game_data)
    return [
        ToolStockOut(
            generation=s.generation,
            generation_label=ef.generation(s.generation).label,
            source=s.source,
            tools=s.tools,
            book_cents=s.value_cents,
        )
        for s in state.tool_stock
        if s.company_id in group and s.tools > 0
    ]


def controls_out(state: GameState, data: LoadedData) -> list[ToolControlOut]:
    gd = data.game_data
    ef = ed.equipment_file(gd)
    out = []
    for c in ef.controls:
        if c.turn > state.turn:
            continue
        out.append(
            ToolControlOut(
                key=c.key,
                title=c.title,
                month_label=format_turn(c.turn),
                generation_labels=[ef.generation(c.generation).label],
                destinations=list(c.to),
                in_force=state.turn <= fm.HISTORY_END,
                source=c.source,
            )
        )
    if gd.controls is not None:
        live = {a.key for a in gr.biting(state, gd)}
        for a in gr.visible(state, gd):
            if EUV not in a.rule.goods:
                continue
            out.append(
                ToolControlOut(
                    key=a.key,
                    title=a.rule.title,
                    month_label=format_turn(a.start_turn),
                    generation_labels=[g.label for g in ef.queued()],
                    destinations=[str(t) if isinstance(t, str) else t.entity for t in a.rule.to],
                    in_force=a.key in live,
                    source=a.rule.source,
                )
            )
    return out


def _end_window(prog: Programme, p: ProgrammeDef, data: LoadedData) -> str:
    """Public: the stage's months range x the overrun range, at its funding (never its draw)."""
    pb = data.balance.equipment.programme
    f = max(prog.funding, 1e-9)
    lo = prog.started_turn + round(p.months[0] * pb.work_scale * (1 + pb.overrun.lo) / f)
    hi = prog.started_turn + round(p.months[1] * pb.work_scale * (1 + pb.overrun.hi) / f)
    return f"{format_turn(lo)} to {format_turn(hi)}, if fully staffed"


def programme_out(state: GameState, data: LoadedData) -> LithoProgrammeOut:
    b, gd = data.balance, data.game_data
    ef = ed.equipment_file(gd)
    pb = b.equipment.programme
    cid = state.player.id
    company = state.company(cid)
    unlock: str | None = None
    if company.stage < pb.min_stage:
        unlock = f"Opens at stage {pb.min_stage} with a chip product and a fab"
    elif not ep.has_chip_and_fab(state, cid):
        unlock = "Opens with a chip product and a fab"
    staff = ep.staffing(state, cid, b, gd) if unlock is None else ep.Staffing(0, 0.0)
    stages = []
    for p in ef.programme:
        run = ep.latest(state, cid, p.key)
        why = None if unlock is not None else ep.why_not(state, cid, p.key, b, gd)
        status = "locked" if unlock is not None else ("open" if why is None else "locked")
        if run is not None:
            status = run.status if run.status != "running" else "running"
            if run.status in ("failed", "stopped") and why is None:
                status = "open"
        done = run is not None and run.status == "succeeded"
        stages.append(
            LithoStageOut(
                key=p.key,
                label=p.label,
                generation_label=ef.generation(p.generation).label,
                after_stage=ef.stage(p.needs).label if p.needs else None,
                cost_cents=p.cost,
                months_low=p.months[0],
                months_high=p.months[1],
                level=p.level,
                staff=p.staff,
                reference_cents=round(ep.reference_cents(p, b)),
                status=status,
                attempt=run.attempt if run else 0,
                started_label=format_turn(run.started_turn) if run else None,
                months_running=(
                    (run.ended_turn or state.turn) - run.started_turn + 1 if run else None
                ),
                funding=run.funding if run else None,
                spent_cents=run.spent_cents if run else 0,
                end_window_label=_end_window(run, p, data)
                if run and run.status == "running"
                else None,
                why_not=why if status in ("locked", "open") else None,
                throughput=run.throughput if done and run else None,
                yield_cut=run.yield_cut if done and run else None,
            )
        )
    lines = []
    for x in state.own_tools:
        if x.company_id != cid:
            continue
        installed = sum(
            t.tools
            for t in state.fab_tools
            if t.source == "own"
            and t.generation == x.generation
            and (f := fm.fab_of(state, t.facility_id)) is not None
            and f.company_id == cid
        )
        lines.append(
            OwnToolsOut(
                stage=ef.stage(x.stage).label,
                generation_label=ef.generation(x.generation).label,
                made=x.made,
                in_stock=stock.held(state, cid, x.generation, "own"),
                installed=installed,
                sold=x.sold,
                sales_cents=x.sales_cents,
                maturity=round(ep.maturity(x, b), 3),
                throughput=round(ep.own_throughput(state, x, b), 3),
                yield_cut=round(ep.own_yield_cut(state, x, b), 1),
                per_year=ef.stage(x.stage).tools_per_year,
            )
        )
    return LithoProgrammeOut(
        unlocked=unlock is None,
        unlock_reason=unlock,
        level=round(ep.level(state, cid, b, gd), 1),
        researchers=staff.researchers,
        funding_low=pb.funding.lo,
        funding_high=pb.funding.hi,
        stages=stages,
        own_tools=lines,
    )


def equipment_out(state: GameState, data: LoadedData) -> EquipmentOut:
    ef = ed.equipment_file(data.game_data)
    qb = data.balance.equipment.queue
    return EquipmentOut(
        turn=state.turn,
        supplier=ef.supplier("asml").name,
        generations=generations_out(state, data),
        orders=orders_out(state, data),
        stock=stock_out(state, data),
        controls=controls_out(state, data),
        programme=programme_out(state, data),
        prepay_share=qb.prepay_share,
        max_order=qb.max_order,
        order_energy=qb.energy,
        note=NOTE,
    )


def months_label(months: int) -> str:
    return (
        f"{months // MONTHS} years {months % MONTHS} months"
        if months >= MONTHS
        else f"{months} months"
    )
