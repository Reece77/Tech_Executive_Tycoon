"""Fabs and their tools (docs/formulas.md 47.2, 47.4; M21's 38.2 `euv_tools` good replaced).

A fab at a node a queued generation serves needs `ceil(starts / fab.euv.wafers_per_tool)` of its
tools. Ordering (a new fab, or a conversion to such a node) takes them in this order:

1. the company's ASML tools in stock (their book value moves 1530 -> 1500, and the fab's capex
   falls by their value at today's price, at most `programme.tool_capex_share` of it);
2. with `own_tools`, its own tools in stock (a tool counts `own throughput` of one; they skip the
   queue and the controls on ASML's tools);
3. the rest as an order in ASML's queue for the fab, at today's price, locked. Its cost stays
   inside the fab's capex, as before M33, except that from `equipment.start` the order's price
   above the list (scarcity) or below it (ASML's response) changes the capex by
   `tools x (price - list)`, and a prepayment adds `prepay_share x price x tools`.

The fab completes no earlier than its last tool's delivery plus `fab.euv.install_months`; a
conversion likewise. While an order is open the phase keeps the fab's `live_turn` (or conversion's
`upgrade_ready`) at least a quarter and the installation away.

A live fab's starts on offer are x its tools' factor: ASML's tools x (1 - service ban cut when a
ban on EUV tools covers its country), its own tools x (own uptime / ASML's) x (1 - own yield
cut / its yield) (M33 decision: a lower yield read as fewer good starts, so the cost per good die
rises as 47.4 asks).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.equipment import controls as ec
from tst.sim.equipment import data as ed
from tst.sim.equipment import programme as ep
from tst.sim.equipment import queue as eq
from tst.sim.equipment import stock
from tst.sim.equipment.config import EPS
from tst.sim.equipment.models import FabTools, ToolOrder
from tst.sim.fabs.models import Fab
from tst.sim.ledger import PPE, LedgerEntry
from tst.sim.money import times
from tst.sim.state import GameState

POINTS: Final = 100.0  # tunable-exempt: yield points per unit of yield


@dataclass(frozen=True, slots=True)
class ToolPlan:
    """What a fab order's tools would be (no hidden value: the lead is a range)."""

    generation: str | None
    tools: int  # ASML-equivalent tools the fab needs
    from_stock: int
    from_own: int
    to_order: int
    price_cents: int
    list_cents: int
    lead_low: int | None  # months to the last tool, fast end of the range
    lead_high: int | None
    blocked: str | None
    tools_turn: int | None  # the plan's month for the last tool (the slow end)
    stock_value_cents: int = 0
    capex_cut_cents: int = 0


def needed(capacity: int, balance: Balance) -> int:
    return math.ceil(capacity / balance.fab.euv.wafers_per_tool)


def plan(
    state: GameState,
    company_id: int,
    node: str,
    tools: int,
    country: str,
    balance: Balance,
    data: GameData,
    *,
    own: bool = False,
    prepay: bool = False,
    have_generation: str | None = None,
    have_tools: int = 0,
) -> ToolPlan:
    """The tools a fab order at `node` takes (module docstring); `tools` are ASML-equivalent."""
    g = ed.generation_for(data, node)
    if g is None or tools <= 0:
        return ToolPlan(None, 0, 0, 0, 0, 0, 0, 0, 0, None, None)
    if have_generation == g.key:
        tools = max(0, tools - have_tools)
    asml = stock.held(state, company_id, g.key, "asml")
    from_stock = min(asml, tools)
    left = tools - from_stock
    from_own = 0
    if own and left > 0:
        lt = ep.line(state, company_id, g.key)
        if lt is not None:
            t = ep.own_throughput(state, lt, balance)
            want = math.ceil(left / max(t, EPS))
            from_own = min(stock.held(state, company_id, g.key, "own"), want)
            left = max(0, left - math.floor(from_own * t + EPS))
    price = ed.price_cents(state, g, balance)
    lst = round(ed.base_price_cents(g, state.turn, balance.equipment.price.growth))
    low = high = None
    blocked = None
    turn: int | None = state.turn if left == 0 else None
    if left > 0:
        order = _order(state, company_id, None, g.key, left, country, price, prepay)
        blocked = ec.order_blocked(state, data, order)
        if blocked is None:
            lead = eq.lead(state, order, balance, data)
            low, high = lead.low, lead.high
            turn = None if high is None else state.turn + high
    value = 0
    if from_stock:
        rec = next(
            (
                s
                for s in state.tool_stock
                if s.company_id == company_id and s.generation == g.key and s.source == "asml"
            ),
            None,
        )
        if rec is not None and rec.tools:
            value = rec.value_cents * from_stock // rec.tools
    return ToolPlan(
        g.key,
        tools,
        from_stock,
        from_own,
        left,
        price,
        lst,
        low,
        high,
        blocked,
        turn,
        stock_value_cents=value,
        capex_cut_cents=from_stock * price,
    )


def _order(
    state: GameState,
    company_id: int,
    facility_id: int | None,
    generation: str,
    tools: int,
    country: str,
    price: int,
    prepay: bool,
) -> ToolOrder:
    return ToolOrder(
        id=eq.next_order_id(state),
        buyer=eq.PLAYER,
        generation=generation,
        tools=tools,
        placed_turn=state.turn,
        company_id=company_id,
        facility_id=facility_id,
        country=country,
        price_cents=price,
        prepaid=prepay,
    )


def capex_change(p: ToolPlan, capex_cents: int, balance: Balance, state: GameState) -> int:
    """The fab's capex change from its tools (module docstring): stock saves, scarcity and a
    prepayment cost."""
    eb = balance.equipment
    cut = min(p.capex_cut_cents, times(capex_cents, eb.programme.tool_capex_share))
    own_cut = 0
    if p.from_own and p.generation is not None:
        own_cut = min(
            p.from_own * p.list_cents, times(capex_cents, eb.programme.tool_capex_share) - cut
        )
    extra = 0
    if p.to_order and state.turn >= eb.start_turn:
        extra = p.to_order * (p.price_cents - p.list_cents)
    return extra - cut - max(0, own_cut)


def prepay_cents(p: ToolPlan, balance: Balance) -> int:
    return times(p.price_cents * p.to_order, balance.equipment.queue.prepay_share)


def commit(
    state: GameState,
    company_id: int,
    facility_id: int,
    p: ToolPlan,
    country: str,
    prepay: bool,
) -> tuple[GameState, list[LedgerEntry]]:
    """Take the plan's stock and place its order for the fab (module docstring)."""
    entries: list[LedgerEntry] = []
    if p.generation is None:
        return state, entries
    if p.from_stock:
        state, n, value = stock.take(state, company_id, p.generation, p.from_stock, "asml")
        if value:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=company_id,
                    memo="Tools from stock into a fab",
                    debit=PPE,
                    credit=stock.TOOLS_ACCOUNT,
                    amount=value,
                )
            )
        state = add_fab_tools(state, facility_id, p.generation, n, "asml")
    if p.from_own:
        state, n, value = stock.take(state, company_id, p.generation, p.from_own, "own")
        if value:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=company_id,
                    memo="Own lithography tools into a fab",
                    debit=PPE,
                    credit=stock.TOOLS_ACCOUNT,
                    amount=value,
                )
            )
        state = add_fab_tools(state, facility_id, p.generation, n, "own")
    if p.to_order:
        order = _order(
            state, company_id, facility_id, p.generation, p.to_order, country, p.price_cents, prepay
        )
        state = replace(state, tool_orders=(*state.tool_orders, order))
    return state, entries


def add_fab_tools(
    state: GameState, facility_id: int, generation: str, tools: int, source: str
) -> GameState:
    if tools <= 0:
        return state
    out = []
    found = False
    for x in state.fab_tools:
        if x.facility_id == facility_id and x.generation == generation and x.source == source:
            x = replace(x, tools=x.tools + tools)
            found = True
        out.append(x)
    if not found:
        out.append(FabTools(facility_id, generation, tools, "own" if source == "own" else "asml"))
    return replace(state, fab_tools=tuple(out))


def retire_other_generations(state: GameState, facility_id: int, generation: str) -> GameState:
    """A conversion to another generation's node leaves the old tools idle (M33 decision: they
    are part of the old capex, depreciating as before)."""
    return replace(
        state,
        fab_tools=tuple(
            x for x in state.fab_tools if x.facility_id != facility_id or x.generation == generation
        ),
    )


def open_order(state: GameState, facility_id: int) -> ToolOrder | None:
    return next(
        (o for o in state.tool_orders if o.facility_id == facility_id and o.status == "open"),
        None,
    )


def lost_order(state: GameState, facility_id: int) -> ToolOrder | None:
    return next(
        (o for o in state.tool_orders if o.facility_id == facility_id and o.status == "lost"),
        None,
    )


def tools_factor(state: GameState, fab: Fab, balance: Balance, data: GameData) -> float:
    """A live fab's starts on offer factor from its tools (module docstring); 1 without any."""
    mine = [x for x in state.fab_tools if x.facility_id == fab.facility_id]
    total = sum(x.tools for x in mine)
    if total <= 0:
        return 1.0
    facility = state.facility(fab.facility_id)
    country = None
    if facility is not None and data.countries is not None:
        from tst.sim.geopolitics.world import facility_country

        country = facility_country(state, facility, data)
    out = 0.0
    for x in mine:
        g = ed.equipment_file(data).generation(x.generation)
        if x.source == "own":
            line = ep.line(state, fab.company_id, x.generation)
            if line is None:
                out += x.tools
                continue
            asml_up = ed.uptime(g, state.turn)
            up = ep.own_uptime(state, line, asml_up, balance) / asml_up
            cut = ep.own_yield_cut(state, line, balance) / POINTS
            y = max(fab.yield_, EPS)
            out += x.tools * up * max(0.0, 1 - cut / y)
        else:
            f = 1.0 if country is None else ec.uptime_factor(state, data, country, balance)
            out += x.tools * f
    return out / total
