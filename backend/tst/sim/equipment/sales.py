"""The player's own tools sold to rival foundries (docs/formulas.md 47.4), each December.

From `litho_2` (a line of a queued generation), when ASML's open orders of the generation exceed
`sales.min_backlog_years` x next year's capacity and the line's tools are at least
`sales.min_quality` of ASML's throughput, rivals buy
`floor(share x quality x rivals' open tools)` from the company's own stock, at ASML's price x
(1 - `sales.discount`): revenue to 4430, the tools' made cost from 1530 to 5200. What they buy
comes off their open orders (largest first). ASML responds the next December
(tst.sim.equipment.capacity: a price cut and a faster newest generation).
"""

from __future__ import annotations

import math
from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.equipment import data as ed
from tst.sim.equipment import programme as ep
from tst.sim.equipment import stock
from tst.sim.equipment.models import Delivery, OwnTools
from tst.sim.equipment.queue import DECEMBER, PLAYER
from tst.sim.ledger import CASH, TOOL_COST, TOOL_SALES, LedgerEntry, LedgerLine
from tst.sim.money import exact, times
from tst.sim.state import GameState

RIVALS = "rivals"  # tunable-exempt: a sale's buyer in the deliveries history


def december(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[tuple[OwnTools, int, int]]]:
    if state.turn % 12 != DECEMBER or not state.own_tools:
        return state, [], []
    sb = balance.equipment.sales
    ef = ed.equipment_file(data)
    entries: list[LedgerEntry] = []
    sold_rows: list[tuple[OwnTools, int, int]] = []
    lines = []
    for x in state.own_tools:
        g = ef.generation(x.generation)
        if not g.queued:
            lines.append(x)
            continue
        quality = ep.own_throughput(state, x, balance)
        nxt = max(1, ed.capacity(state, g, ed.year_of(state.turn) + 1))
        book = ed.open_tools(state, g.key)
        rival = [
            o
            for o in state.tool_orders
            if o.generation == g.key and o.status == "open" and o.buyer != PLAYER
        ]
        unmet = sum(o.remaining for o in rival)
        have = stock.held(state, x.company_id, g.key, "own")
        if quality < sb.min_quality or book < sb.min_backlog_years * nxt or have <= 0:
            lines.append(x)
            continue
        n = min(have, math.floor(sb.share * quality * unmet))
        if n <= 0:
            lines.append(x)
            continue
        price = times(ed.price_cents(state, g, balance), 1 - exact(sb.discount))
        state, n, value = stock.take(state, x.company_id, g.key, n, "own")
        revenue = price * n
        entries.append(
            LedgerEntry(
                state.turn,
                x.company_id,
                f"Own lithography tools sold to rival foundries: {n}",
                (
                    LedgerLine(CASH, revenue),
                    LedgerLine(TOOL_SALES, -revenue),
                    LedgerLine(TOOL_COST, value),
                    LedgerLine(stock.TOOLS_ACCOUNT, -value),
                ),
            )
        )
        left = n
        orders = {o.id: o for o in state.tool_orders}
        for o in sorted(rival, key=lambda o: (-o.remaining, o.id)):
            take = min(left, o.remaining)
            if take <= 0:
                break
            new_tools = o.tools - take
            orders[o.id] = replace(
                o,
                tools=new_tools,
                status="done" if new_tools <= o.delivered else "open",
                done_turn=state.turn if new_tools <= o.delivered else None,
            )
            left -= take
        state = replace(
            state,
            tool_orders=tuple(sorted(orders.values(), key=lambda o: o.id)),
            tool_deliveries=(
                *state.tool_deliveries,
                Delivery(state.turn, RIVALS, g.key, n, x.company_id, "own"),
            ),
        )
        x = replace(x, sold=x.sold + n, sales_cents=x.sales_cents + revenue)
        lines.append(x)
        sold_rows.append((x, n, revenue))
    return replace(state, own_tools=tuple(lines)), entries, sold_rows
