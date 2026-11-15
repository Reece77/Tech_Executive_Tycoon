"""M33's month (docs/formulas.md 47), in phase 4 before the fabs (so this quarter's tools count
for a fab completing this month).

1. ASML's December rule sets next year's capacity (from `equipment.start`; capacity.py).
2. Rivals' December orders (and the 2010 book at turn 0; queue.py).
3. In a quarter's first month: blocked orders are lost, the quarter's tools are allocated, and
   each delivery reaches its fab (or the company's stock, paid at delivery: cash to 1530).
4. A fab whose order is still open waits: its live month (or conversion) stays at least the next
   quarter plus installation away; once its last tool arrives it is due that plus installation.
5. The lithography programme's stages spend and progress; own tool lines make tools; installed
   own tools gain tool-months (the learning curve).
6. Each December the player's own tools sell to rivals (sales.py).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.equipment import capacity, fablink, programme, queue, sales, stock
from tst.sim.equipment import data as ed
from tst.sim.equipment.data import QUARTER_MONTHS
from tst.sim.equipment.models import ToolOrder
from tst.sim.fabs import market as fm
from tst.sim.group.assets import inbox_company
from tst.sim.ledger import CASH, GENERAL_ADMIN, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_fab


def _supplier(data: GameData, generation: str) -> str:
    ef = ed.equipment_file(data)
    return ef.supplier(ef.generation(generation).maker).name


def _label(data: GameData, generation: str) -> str:
    return ed.equipment_file(data).generation(generation).label


def _target(state: GameState, order: ToolOrder, balance: Balance, data: GameData) -> str:
    if order.facility_id is None:
        return " into stock"
    fab = fm.fab_of(state, order.facility_id)
    if fab is None:
        return ""
    from tst.sim.fabs.plants import fab_name

    return f" for {fab_name(state, fab, balance, data)}"


def _deliver(
    state: GameState,
    order: ToolOrder,
    before: ToolOrder,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], LogItem | None]:
    """A player order's tools this quarter reach its fab or the stock."""
    n = order.delivered - before.delivered
    entries: list[LedgerEntry] = []
    assert order.company_id is not None
    if order.facility_id is None:
        value = n * order.price_cents + order.prepaid_cents * n // order.tools
        state = stock.add(state, order.company_id, order.generation, n, "asml", value)
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=order.company_id,
                memo=f"{_supplier(data, order.generation)} tools into stock: {n}",
                debit=stock.TOOLS_ACCOUNT,
                credit=CASH,
                amount=value,
            )
        )
    else:
        state = fablink.add_fab_tools(state, order.facility_id, order.generation, n, "asml")
        state = _fab_due(state, order, balance)
    left = (
        "The order is complete."
        if order.status == "done"
        else f"{order.remaining} more are on order."
    )
    log = inbox_item(
        state.turn,
        inbox_company(state, order.company_id),
        "tools_delivered",
        link_kind="equipment",
        link_id=order.id,
        tools=n,
        generation=_label(data, order.generation),
        supplier=_supplier(data, order.generation),
        target=_target(state, order, balance, data),
        left=left,
    )
    return state, entries, log


def _fab_due(state: GameState, order: ToolOrder, balance: Balance) -> GameState:
    """A fab's live month (or conversion) once its order is complete (module docstring 4)."""
    if order.status != "done" or order.facility_id is None:
        return state
    fab = fm.fab_of(state, order.facility_id)
    if fab is None:
        return state
    install = balance.fab.euv.install_months
    due = state.turn + install
    if fab.upgrade_started is not None and fab.upgrade_ready is not None:
        base = fab.upgrade_started + balance.fab.upgrade.months
        return with_fab(state, replace(fab, tools_turn=state.turn, upgrade_ready=max(base, due)))
    facility = state.facility(fab.facility_id)
    build_end = (facility.ordered_turn if facility else state.turn) + fab.build_months
    return with_fab(state, replace(fab, tools_turn=state.turn, live_turn=max(build_end, due)))


def _waiting(state: GameState, balance: Balance) -> GameState:
    """Fabs whose orders are open stay at least the next quarter + installation away."""
    install = balance.fab.euv.install_months
    nxt = state.turn + QUARTER_MONTHS - state.turn % QUARTER_MONTHS
    latest: dict[int, ToolOrder] = {}
    for o in state.tool_orders:
        if o.facility_id is not None and o.buyer == queue.PLAYER:
            latest[o.facility_id] = o  # ids ascend: the fab's latest order
    for o in latest.values():
        if o.status not in ("open", "lost") or o.facility_id is None:
            continue  # a lost order's fab waits until a new order for it completes
        fab = fm.fab_of(state, o.facility_id)
        if fab is None:
            continue
        floor = nxt + install
        if fab.upgrade_started is not None and fab.upgrade_ready is not None:
            if fab.upgrade_ready < floor:
                state = with_fab(state, replace(fab, upgrade_ready=floor))
        elif fab.live_turn < floor:
            state = with_fab(state, replace(fab, live_turn=floor))
    return state


def _learn_own(state: GameState) -> GameState:
    """Installed own tools in live fabs add a tool-month each to their line."""
    if not state.own_tools:
        return state
    months: dict[tuple[int, str], float] = {}
    for x in state.fab_tools:
        if x.source != "own":
            continue
        fab = fm.fab_of(state, x.facility_id)
        facility = state.facility(x.facility_id)
        if fab is None or facility is None or facility.status != "live":
            continue
        key = (fab.company_id, x.generation)
        months[key] = months.get(key, 0.0) + x.tools
    lines = tuple(
        replace(t, tool_months=t.tool_months + months.get((t.company_id, t.generation), 0.0))
        for t in state.own_tools
    )
    return replace(state, own_tools=lines)


def equipment_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not ed.enabled(data):
        return state, [], []
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    state = queue.catch_up(state, balance, data)
    state = capacity.december(state, balance, data)
    state = queue.december_orders(state, balance, data)
    if ed.is_quarter_start(state.turn):
        before = {o.id: o for o in state.tool_orders}
        state, served, lost = queue.quarter(state, rng, balance, data)
        for o in served:
            if o.buyer != queue.PLAYER:
                continue
            state, more, log = _deliver(state, o, before[o.id], balance, data)
            entries += more
            if log is not None:
                logs.append(log)
        for o, why in lost:
            if o.buyer != queue.PLAYER or o.company_id is None:
                continue
            forfeit = o.prepaid_cents * o.remaining // o.tools
            if forfeit:
                entries.append(
                    LedgerEntry.transfer(
                        turn=state.turn,
                        company_id=o.company_id,
                        memo="Tool prepayment forfeited: order lost to export controls",
                        debit=GENERAL_ADMIN,
                        credit=stock.TOOLS_ACCOUNT,
                        amount=forfeit,
                    )
                )
            logs.append(
                inbox_item(
                    state.turn,
                    inbox_company(state, o.company_id),
                    "tools_order_lost",
                    link_kind="equipment",
                    link_id=o.id,
                    rule=why,
                    supplier=_supplier(data, o.generation),
                    left=o.remaining,
                    generation=_label(data, o.generation),
                    target=_target(state, o, balance, data),
                )
            )
    state = _waiting(state, balance)
    state, more, ended = programme.month(state, rng, balance, data)
    entries += more
    ef = ed.equipment_file(data)
    for prog, outcome in ended:
        p = ef.stage(prog.stage)
        company = inbox_company(state, prog.company_id)
        if outcome == "succeeded":
            logs.append(
                inbox_item(
                    state.turn,
                    company,
                    "litho_succeeded",
                    link_kind="equipment",
                    stage=p.label,
                    throughput=f"{prog.throughput:.0%}",
                    yield_cut=f"{prog.yield_cut:.0f}",
                    per_year=p.tools_per_year,
                )
            )
        else:
            logs.append(
                inbox_item(
                    state.turn,
                    company,
                    "litho_failed",
                    link_kind="equipment",
                    stage=p.label,
                    months=f"{state.turn - prog.started_turn + 1} months",
                    spent_cents=prog.spent_cents,
                )
            )
    state, more = programme.produce(state, balance, data)
    entries += more
    state = _learn_own(state)
    state, more, sold = sales.december(state, balance, data)
    entries += more
    for line, n, revenue in sold:
        logs.append(
            inbox_item(
                state.turn,
                inbox_company(state, line.company_id),
                "tools_sold",
                link_kind="equipment",
                tools=n,
                generation=_label(data, line.generation),
                cents=revenue,
            )
        )
    return state, entries, logs


def when(turn: int | None) -> str:
    return format_turn(turn) if turn is not None else "not yet known"
