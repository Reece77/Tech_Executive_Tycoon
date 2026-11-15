"""Explain for M33's queue (docs/formulas.md 47.2, 47.6): why a tool order waits. Public facts
only: the order's lead-time range, its tools still due, ASML's capacity this year and next once
announced and the depth of its book, in words; never the order's place or weight."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Explanation, Item, MetricDef
from tst.advisor.v3 import _bad, _id, _none
from tst.sim.equipment import data as ed
from tst.sim.equipment import queue as eq
from tst.sim.geopolitics import world

if TYPE_CHECKING:
    from tst.advisor.build import Builder


def tool_wait(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """An open order's months to its last tool (the slow end of its range), and what sets it."""
    if not entity:
        return _none(b, m, "tool order")
    oid = _id(entity, "tool order")
    d, bal = b.data.game_data, b.data.balance
    group = {c.id for c in world.group(b.state)} if world.enabled(d) else {b.state.player.id}
    order = next((o for o in b.state.tool_orders if o.id == oid), None)
    if order is None or order.buyer != eq.PLAYER or order.company_id not in group:
        raise _bad(f"no tool order {oid} of your group")
    g = ed.equipment_file(d).generation(order.generation)
    year = ed.year_of(b.state.turn)
    items = [
        Item("Tools still due on the order", float(order.remaining), "count"),
        Item(
            f"{g.label} tools ASML makes this year", float(ed.capacity(b.state, g, year)), "count"
        ),
        Item(
            "Open orders in ASML's book (every buyer)",
            float(ed.open_tools(b.state, g.key)),
            "count",
        ),
    ]
    value: float | None = None
    if order.status == "open":
        lead = eq.lead(b.state, order, bal, d)
        if lead.low is not None:
            items.append(Item("Fast end of the range", float(lead.low), "months"))
        if lead.high is not None:
            items.append(Item("Slow end of the range", float(lead.high), "months"))
            value = float(lead.high)
    note = (
        "Each quarter ASML ships its tools to open orders in queue order. An order's place is the "
        "month it was placed, moved up by the buyer's deliveries over the last "
        f"{bal.equipment.queue.history_years} years and by a prepayment: long-standing customers' "
        "orders each December can overtake a new buyer's. "
        + ("This order is prepaid." if order.prepaid else "Prepaying would move it up.")
    )
    return b._out(m, entity, value, items, note, (), [], f"{g.label} order {order.id}")
